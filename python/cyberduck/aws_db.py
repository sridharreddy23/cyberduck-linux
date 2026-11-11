"""
SQLite Database Storage for AWS Accounts, IAM Roles, and STS Credentials.
Eliminates all GUI freezes, hangs, and network delays by keeping accounts
and roles locally cached in ~/.duck/aws_sso.db.
"""
import os
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any

DB_PATH = Path.home() / ".duck" / "aws_sso.db"


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            account_name TEXT,
            email TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT,
            role_name TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, role_name)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS credentials_cache (
            account_id TEXT,
            role_name TEXT,
            access_key_id TEXT,
            secret_access_key TEXT,
            session_token TEXT,
            expiration INTEGER,
            PRIMARY KEY(account_id, role_name)
        )
        """)
        conn.commit()
    finally:
        conn.close()


def find_active_sso_token() -> Tuple[Optional[str], str]:
    """Find non-expired SSO token in ~/.aws/sso/cache/."""
    cache_dir = Path.home() / ".aws" / "sso" / "cache"
    if not cache_dir.exists():
        return None, "us-east-1"

    now = datetime.now(timezone.utc)
    for f in cache_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            if "accessToken" in d and "startUrl" in d:
                exp_str = d.get("expiresAt", "")
                if exp_str:
                    exp = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                    if exp > now:
                        return d["accessToken"], d.get("region", "us-east-1")
        except Exception:
            pass
    return None, "us-east-1"


def find_active_sso_start_url() -> Optional[str]:
    """Find startUrl from ~/.aws/sso/cache/ or ~/.aws/config."""
    cache_dir = Path.home() / ".aws" / "sso" / "cache"
    if cache_dir.exists():
        for f in cache_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text())
                if "startUrl" in d and d["startUrl"]:
                    return d["startUrl"]
            except Exception:
                pass
    cfg = Path.home() / ".aws" / "config"
    if cfg.exists():
        try:
            import re
            m = re.search(r'sso_start_url\s*=\s*(https?://\S+)', cfg.read_text())
            if m:
                return m.group(1).strip()
        except Exception:
            pass
    return None


def get_all_accounts() -> List[Dict[str, str]]:
    """Instant query of all cached accounts from SQLite."""
    init_db()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT account_id, account_name, email FROM accounts ORDER BY account_name ASC")
        rows = cur.fetchall()
        return [{"accountId": r["account_id"], "accountName": r["account_name"], "email": r["email"]} for r in rows]
    finally:
        conn.close()


def get_roles_for_account(account_id: str) -> List[str]:
    """Instant query of all cached roles for an account from SQLite."""
    init_db()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT role_name FROM roles WHERE account_id = ? ORDER BY role_name ASC", (account_id,))
        rows = cur.fetchall()
        return [r["role_name"] for r in rows]
    finally:
        conn.close()


def get_cached_credentials(account_id: str, role_name: str) -> Optional[Dict[str, str]]:
    """Get active STS credentials if unexpired (with 60-second grace buffer)."""
    init_db()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        now_ts = int(datetime.now(timezone.utc).timestamp())
        cur.execute(
            "SELECT access_key_id, secret_access_key, session_token, expiration FROM credentials_cache WHERE account_id = ? AND role_name = ?",
            (account_id, role_name)
        )
        row = cur.fetchone()
        if row:
            exp = row["expiration"] or 0
            if exp > (now_ts + 60):
                return {
                    "access_key": row["access_key_id"],
                    "secret_key": row["secret_access_key"],
                    "session_token": row["session_token"],
                }
        return None
    finally:
        conn.close()


def save_cached_credentials(account_id: str, role_name: str, ak: str, sk: str, st: str, expiration_ms: int):
    """Save STS credentials to SQLite cache."""
    init_db()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # expiration in seconds
        exp_sec = int(expiration_ms / 1000) if expiration_ms > 1000000000000 else int(expiration_ms)
        cur.execute(
            """
            INSERT OR REPLACE INTO credentials_cache
            (account_id, role_name, access_key_id, secret_access_key, session_token, expiration)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (account_id, role_name, ak, sk, st, exp_sec)
        )
        conn.commit()
    finally:
        conn.close()


def fetch_and_cache_role_credentials(account_id: str, role_name: str) -> Optional[Dict[str, str]]:
    """Fetch fresh STS credentials from AWS SSO and update local DB cache."""
    token, region = find_active_sso_token()
    if not token:
        return None

    try:
        res = subprocess.run(
            ["aws", "sso", "get-role-credentials", "--access-token", token, "--account-id", account_id, "--role-name", role_name, "--region", region],
            capture_output=True, text=True, timeout=8
        )
        if res.returncode == 0:
            c = json.loads(res.stdout).get("roleCredentials", {})
            ak = c.get("accessKeyId", "")
            sk = c.get("secretAccessKey", "")
            st = c.get("sessionToken", "")
            exp = c.get("expiration", 0)
            if ak and sk:
                save_cached_credentials(account_id, role_name, ak, sk, st, exp)
                return {"access_key": ak, "secret_key": sk, "session_token": st}
    except Exception:
        pass
    return None


def sync_all_accounts_and_roles(token: str, region: str = "us-east-1", callback=None) -> int:
    """Sync all AWS accounts and roles into SQLite DB."""
    init_db()
    res = subprocess.run(
        ["aws", "sso", "list-accounts", "--access-token", token, "--region", region],
        capture_output=True, text=True, timeout=12
    )
    if res.returncode != 0:
        return 0

    accs = json.loads(res.stdout).get("accountList", [])
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        total_accounts = len(accs)
        for idx, a in enumerate(accs, 1):
            aid = a["accountId"]
            aname = a["accountName"]
            email = a.get("emailAddress", "")
            cur.execute("INSERT OR REPLACE INTO accounts (account_id, account_name, email) VALUES (?, ?, ?)", (aid, aname, email))

            res_r = subprocess.run(
                ["aws", "sso", "list-account-roles", "--access-token", token, "--account-id", aid, "--region", region],
                capture_output=True, text=True, timeout=10
            )
            if res_r.returncode == 0:
                roles = json.loads(res_r.stdout).get("roleList", [])
                for r in roles:
                    rname = r.get("roleName")
                    if rname:
                        cur.execute("INSERT OR IGNORE INTO roles (account_id, role_name) VALUES (?, ?)", (aid, rname))
            if callback:
                callback(idx, total_accounts, aname)
        conn.commit()
        return total_accounts
    finally:
        conn.close()

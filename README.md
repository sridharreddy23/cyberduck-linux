# Cyberduck for Linux

[![Release](https://img.shields.io/github/v/release/sridharreddy23/cyberduck-linux?include_prereleases&style=flat-square&color=blue)](https://github.com/sridharreddy23/cyberduck-linux/releases)
[![Debian Package](https://img.shields.io/badge/package-.deb%20(Ubuntu%2FDebian%2FMint)-orange?style=flat-square)](https://github.com/sridharreddy23/cyberduck-linux/releases/tag/v9.6.1-linux)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-green.svg?style=flat-square)](LICENSE.txt)
[![Java Compatibility](https://img.shields.io/badge/Java-17%20%7C%2021%20%7C%2025-blueviolet?style=flat-square)](https://adoptium.net)

Native Cyberduck desktop client for Linux featuring the classic Windows/macOS desktop look & feel, powered by Cyberduck Core and Qt5, with first-class AWS SSO (IAM Identity Center) support.

<p align="center">
  <img src="cyberduck-application-rect.png" alt="Cyberduck Linux Icon" width="160px"/>
</p>

---

## What Problem Does This Solve on Linux?

While Cyberduck is widely celebrated on macOS and Windows as one of the best file transfer and cloud storage clients, Linux users historically faced major gaps:

1. **No Official Linux Desktop UI**: Upstream Cyberduck only provides a command-line interface (`duck`) or experimental prototypes on Linux. Running the Windows version through Wine suffers from latency, broken shortcuts, file dialog glitches, and poor desktop integration.
2. **AWS SSO (IAM Identity Center) Hurdles**: In enterprise cloud environments, authenticating to AWS S3 using AWS SSO with multiple accounts and IAM roles often requires manual terminal commands (`aws sso login`), copying short-lived STS tokens, or re-configuring credentials every time they expire.
3. **Accidental Bucket/Folder Renaming**: In generic tree views, clicking or double-clicking items often inadvertently enters inline rename edit mode, creating risks when browsing critical cloud storage buckets.
4. **Out-of-Order Download Timestamps**: By default, cloud clients preserve remote object timestamps (often months or years old), causing downloaded files to get lost at the bottom of Linux file managers (Nautilus, Dolphin, Nemo) instead of staying at the top of the `~/Downloads` folder.
5. **Java Runtime Mismatches**: Heavyweight Panama / Java 22+ preview bindings frequently break on LTS enterprise Linux distributions running OpenJDK 17 or OpenJDK 21.

### The Solution: Cyberduck for Linux

This repository provides a **fully integrated desktop application** and standalone **Debian (`.deb`) installer**:

- **Native Linux Desktop Experience**: Powered by a robust PyQt5 GUI replicating the authentic Windows Cyberduck interface with full Freedesktop system integration, app menu launcher, and high-resolution icons.
- **Offline SQLite AWS SSO Switcher (`~/.duck/aws_sso.db`)**:
  - Automatically loads and switches between 10+ AWS Accounts and 20+ IAM Roles in < 1 millisecond.
  - Automatically retrieves and caches temporary STS tokens in the background without UI freezes.
  - Generates Cyberduck S3 connection bookmarks automatically for each account and role.
- **Protected File Operations**: Inline rename triggers are disabled on item clicks. Renaming requires an explicit intent via **F2** or **Right-Click → Rename**.
- **Chronological Download Sorting**: Configured to preserve current download timestamps so files always land at the top of your Downloads folder.
- **Universal Java LTS Compatibility**: Bundled backend engine is compiled with Java 17 bytecode and verified across **OpenJDK 17 LTS**, **OpenJDK 21 LTS**, and **OpenJDK 25**.
- **First-Class Multi-Protocol Support**:
  - **Amazon S3 (IAM Identity Center / SSO)**: Seamless browser-based AWS SSO authorization with offline SQLite credential caching.
  - **Amazon S3 (Permanent Credentials)**: Dedicated protocol for standard IAM user `AKIA...` keys without temporary token clutter.
  - **Google Cloud Storage (GCS)**: Direct storage bucket access with Google Cloud interoperability and service account keys.
  - **Microsoft Azure Blob Storage**: Connects directly to Azure storage containers (`blob.core.windows.net`).
  - **Backblaze B2 Cloud Storage**: Connects directly to B2 buckets with Key ID and Application Key.
  - **SFTP (SSH), FTP, FTPS (Explicit TLS), and WebDAV (HTTP/HTTPS)**.
- **Enhanced Bookmarks System**:
  - **Instant Search / Filter**: Filter bookmarks in real time as you type.
  - **Informative Two-Line Items**: Shows protocol badge, account nickname, host, username, and default path.
  - **1-Click Bookmark Duplication**: Clone existing bookmarks to quickly configure new paths or credentials.
  - **Save from Open Connection Dialog**: Directly save any connection profile as a bookmark before or during connection.
  - **Bookmark Current Connection** (<kbd>Ctrl+Shift+B</kbd>): Save an active session's path and host with a single shortcut.
- **S3 Presigned URL Generator**: Quickly generate secure, time-limited presigned URLs (15m, 1h, 6h, 12h, 24h, 3d, 7d) for any remote object with one-click copying and browser preview.

---

## Installation

### Method 1: Install Pre-Built `.deb` (Recommended for Ubuntu / Debian / Mint)

Download and install the latest `.deb` package directly from [GitHub Releases](https://github.com/sridharreddy23/cyberduck-linux/releases):

```bash
# 1. Download the latest release package
wget https://github.com/sridharreddy23/cyberduck-linux/releases/download/v9.6.1-linux/cyberduck_9.6.1-7_amd64.deb

# 2. Install the package
sudo dpkg -i cyberduck_9.6.1-7_amd64.deb

# 3. Resolve any missing system dependencies (PyQt5, JRE)
sudo apt-get install -f
```

#### Launching the Application
- From the system application menu / search: search for **Cyberduck**
- From the terminal:
  ```bash
  cyberduck
  ```

---

## AWS SSO (IAM Identity Center) Setup & Usage

Connecting to AWS S3 using AWS SSO is effortless:

1. **Sign In**: Click **Open Connection** → select **Amazon S3 (IAM Identity Center)** → click **AWS SSO Login**.
2. **Authorize in Browser**: Cyberduck triggers the AWS SSO authentication in your browser. Once approved, all assigned AWS Accounts and Roles are automatically synced to your local SQLite database.
3. **One-Click Switcher**: Select your target **AWS Account** and **IAM Role** from the dropdowns. Fresh STS temporary credentials (`AccessKeyId`, `SecretAccessKey`, `SessionToken`) are loaded automatically.
4. **Save as Bookmark**: Click **Save as Bookmark** to create a 1-click connection profile for future sessions.
5. **Connect**: Click **Apply to Connection** → **Connect**. Your S3 buckets and objects will populate instantly in the file browser.

---

## Generating S3 Presigned URLs

Share direct, secure, time-limited download or upload links with colleagues without making buckets public or creating IAM users:

1. Right-click any file in your S3 bucket (or select the file and press `Ctrl+Shift+U`, or use the **Action** toolbar menu).
2. Choose **Get Presigned URL...**.
3. Select your desired expiration window:
   - **15 Minutes** (ephemeral access)
   - **1 Hour** (default)
   - **6 Hours / 12 Hours / 24 Hours / 3 Days / 7 Days** (maximum allowed by AWS SigV4)
4. Click **Copy URL** to copy the signed URL to your clipboard, or **Open in Browser** to test downloading directly.

---

## Running or Building from Source

### Prerequisites
- Python 3.8+ with PyQt5:
  ```bash
  sudo apt install python3 python3-pyqt5
  ```
- Java Runtime Environment (OpenJDK 17 LTS, 21 LTS, or 25):
  ```bash
  sudo apt install default-jre
  ```

### Run Directly from Git Clone
You can run the application straight from the repository without installing:
```bash
git clone https://github.com/sridharreddy23/cyberduck-linux.git
cd cyberduck-linux
./cyberduck-windows-ui
```

### Build Your Own `.deb` Package
To compile classes and package a fresh `.deb`:
```bash
./scripts/build_deb.sh
```
The output package will be generated at `dist/cyberduck_9.6.1-7_amd64.deb`.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│               Cyberduck Linux Desktop                  │
│       PyQt5 Native GUI (python/cyberduck/ui/)          │
│   - Windows-exact TreeListView & Toolbars             │
│   - Offline SQLite AWS SSO Engine (aws_db.py)          │
│   - Bookmark Manager & Transfers Dialog                │
└───────────────────────────┬────────────────────────────┘
                            │ JSON-RPC (stdin/stdout)
┌───────────────────────────▼────────────────────────────┐
│         Headless Java Daemon (BridgeDaemon.java)       │
│   - ch.cyberduck.linux.BridgeDaemon (Java 17 target)   │
│   - Asynchronous worker execution & session pool       │
└───────────────────────────┬────────────────────────────┘
                            │ Internal Java APIs
┌───────────────────────────▼────────────────────────────┐
│            Cyberduck Core Engine & Protocols           │
│   - ch.cyberduck.core (Transfers, S3, SFTP, WebDAV)   │
│   - Cryptomator Vault layer & credential stores        │
└────────────────────────────────────────────────────────┘
```

---

## License & Credits

- **License**: [GNU General Public License Version 3](LICENSE.txt).
- **Core Engine & Assets**: Developed by [iterate GmbH](https://cyberduck.io) and the Cyberduck open-source community.

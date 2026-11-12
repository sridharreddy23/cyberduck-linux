#!/usr/bin/env bash
#
# Build standalone Cyberduck .deb package for Debian/Ubuntu/Mint
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION="9.6.1-7"
PKG_NAME="cyberduck"
ARCH="amd64"
DIST_DIR="$REPO_ROOT/dist"
STAGING_DIR="$DIST_DIR/deb_staging"
DEB_FILE="$DIST_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "=== Building Cyberduck Debian Package v${VERSION} ==="

# 1. Compile Bridge daemon and Linux helper classes with Java 17 compatibility
echo "[1/7] Compiling Java classes with Java 17 target..."
BUILD_CLASSES="/tmp/cyberduck_deb_classes"
rm -rf "$BUILD_CLASSES"
mkdir -p "$BUILD_CLASSES"

javac --release 17 -cp "$REPO_ROOT/linux/target/jpackage-input/*" -d "$BUILD_CLASSES" \
  "$REPO_ROOT/linux/src/main/java/ch/cyberduck/linux/LinuxResourcesFinder.java" \
  "$REPO_ROOT/linux/src/main/java/ch/cyberduck/linux/XdgBrowserLauncher.java" \
  "$REPO_ROOT/linux/src/main/java/ch/cyberduck/linux/ProtocolChoice.java" \
  "$REPO_ROOT/linux/src/main/java/ch/cyberduck/linux/BridgeDaemon.java"

# Create a clean linux-9.6.1-SNAPSHOT.jar with ONLY Java 17 classes (no leftover Java 25 GTK classes)
jar cf "$REPO_ROOT/linux/target/jpackage-input/linux-9.6.1-SNAPSHOT.jar" -C "$BUILD_CLASSES" .
rm -rf "$BUILD_CLASSES"

# 2. Clean and create staging layout
echo "[2/7] Preparing staging directory..."
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR/opt/cyberduck/bin"
mkdir -p "$STAGING_DIR/opt/cyberduck/lib/app"
mkdir -p "$STAGING_DIR/opt/cyberduck/python"
mkdir -p "$STAGING_DIR/opt/cyberduck/share/img"
mkdir -p "$STAGING_DIR/opt/cyberduck/share/icons"
mkdir -p "$STAGING_DIR/usr/bin"
mkdir -p "$STAGING_DIR/usr/share/applications"
mkdir -p "$STAGING_DIR/usr/share/pixmaps"
mkdir -p "$STAGING_DIR/DEBIAN"

# 3. Copy Java application jars (skipping unused GTK/javagi jars that require Java 22+)
echo "[3/7] Copying Java application jars..."
for j in "$REPO_ROOT"/linux/target/jpackage-input/*.jar; do
    base=$(basename "$j")
    case "$base" in
        adw-*|cairo-*|gdk-*|gdkpixbuf-*|gio-*|glib-*|gmodule-*|gobject-*|graphene-*|gsk-*|gtk-*|harfbuzz-*|pango-*|pangocairo-*)
            # Skip unused Java 22+ Panama GTK binding jars
            ;;
        *)
            cp -a "$j" "$STAGING_DIR/opt/cyberduck/lib/app/"
            ;;
    esac
done

# 4. Copy Python application code (excluding cache)
echo "[4/7] Copying Python application..."
cp -r "$REPO_ROOT/python/cyberduck" "$STAGING_DIR/opt/cyberduck/python/"
find "$STAGING_DIR/opt/cyberduck/python" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING_DIR/opt/cyberduck/python" -name "*.pyc" -delete 2>/dev/null || true

# 5. Copy UI Icons & Assets
echo "[5/7] Copying UI icon assets..."
cp -a "$REPO_ROOT"/img/*.png "$STAGING_DIR/opt/cyberduck/share/img/"

# Generate standard sized system icons using PIL
python3 - <<EOF
from PIL import Image
import os

src = "$REPO_ROOT/cyberduck-application-rect.png"
img = Image.open(src).convert("RGBA")

# Generate sizes: 512, 256, 128, 64, 48
sizes = [512, 256, 128, 64, 48]
for sz in sizes:
    dest_dir = f"$STAGING_DIR/usr/share/icons/hicolor/{sz}x{sz}/apps"
    os.makedirs(dest_dir, exist_ok=True)
    resized = img.resize((sz, sz), Image.Resampling.LANCZOS)
    resized.save(f"{dest_dir}/cyberduck.png", format="PNG")

# Also copy 48x48 to /usr/share/pixmaps and 512x512 to /opt/cyberduck/share/icons
img.resize((48, 48), Image.Resampling.LANCZOS).save("$STAGING_DIR/usr/share/pixmaps/cyberduck.png", format="PNG")
img.resize((512, 512), Image.Resampling.LANCZOS).save("$STAGING_DIR/opt/cyberduck/share/icons/cyberduck.png", format="PNG")
print("Generated Freedesktop icon theme assets.")
EOF

# 6. Create Launchers & Desktop Integration
echo "[6/7] Creating launcher and desktop entries..."

# /opt/cyberduck/bin/cyberduck
cat > "$STAGING_DIR/opt/cyberduck/bin/cyberduck" <<'EOF'
#!/usr/bin/env bash
#
# Cyberduck Launcher for Linux
#
set -e

APP_DIR="/opt/cyberduck"
export PYTHONPATH="$APP_DIR/python:$PYTHONPATH"
export CYBERDUCK_CLASSPATH="$APP_DIR/lib/app/*"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

# Resolve Java (compatible with OpenJDK 17, 21, 25)
if [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
    JAVA_BIN="$JAVA_HOME/bin/java"
elif command -v java >/dev/null 2>&1; then
    JAVA_BIN="java"
else
    for candidate in \
        /usr/lib/jvm/default-java/bin/java \
        /usr/lib/jvm/java-21-openjdk-amd64/bin/java \
        /usr/lib/jvm/java-17-openjdk-amd64/bin/java \
        /usr/lib/jvm/java-25-openjdk-amd64/bin/java; do
        if [ -x "$candidate" ]; then
            JAVA_BIN="$candidate"
            break
        fi
    done
fi

export JAVA_BIN="${JAVA_BIN:-java}"

exec python3 -m cyberduck.main "$@"
EOF
chmod 755 "$STAGING_DIR/opt/cyberduck/bin/cyberduck"

# Symlink /usr/bin/cyberduck
ln -sf /opt/cyberduck/bin/cyberduck "$STAGING_DIR/usr/bin/cyberduck"

# Desktop entry
cat > "$STAGING_DIR/usr/share/applications/cyberduck.desktop" <<'EOF'
[Desktop Entry]
Name=Cyberduck
GenericName=File Transfer Client
Comment=Libre File Transfer Client for SFTP, FTP, Amazon S3, WebDAV & Cloud Storage
Exec=/opt/cyberduck/bin/cyberduck %U
Icon=cyberduck
Terminal=false
Type=Application
Categories=Network;FileTransfer;
StartupNotify=true
StartupWMClass=Cyberduck
MimeType=x-scheme-handler/sftp;x-scheme-handler/ftp;x-scheme-handler/ftps;x-scheme-handler/dav;x-scheme-handler/davs;
Keywords=FTP;SFTP;S3;AWS;WebDAV;Cloud;Transfer;
EOF

# Calculate installed size in KB
INSTALLED_SIZE=$(du -sk "$STAGING_DIR" | cut -f1)

# Control file
cat > "$STAGING_DIR/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: Cyberduck Project <support@cyberduck.io>
Depends: python3, python3-pyqt5, default-jre (>= 2:1.17) | openjdk-21-jre | openjdk-17-jre | openjdk-25-jre
Replaces: cyberduck (<= 9.6.1)
Conflicts: cyberduck (<< ${VERSION})
Homepage: https://cyberduck.io
Description: Libre file transfer client for Linux, macOS and Windows
 Cyberduck is a libre server and cloud storage browser for SFTP, FTP,
 Amazon S3, Google Cloud Storage, Microsoft Azure & OneDrive, Dropbox,
 WebDAV, Backblaze B2, and OpenStack Swift.
 .
 This package features the native desktop UI with full Windows OS look & feel,
 high-performance multi-threaded transfers, and integrated AWS SSO (IAM Identity Center) support.
EOF

# Maintainer scripts
cat > "$STAGING_DIR/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    chmod 755 /opt/cyberduck/bin/cyberduck || true
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
fi
exit 0
EOF
chmod 755 "$STAGING_DIR/DEBIAN/postinst"

cat > "$STAGING_DIR/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
fi
exit 0
EOF
chmod 755 "$STAGING_DIR/DEBIAN/postrm"

# 7. Build deb package
echo "[7/7] Building deb package with dpkg-deb..."
find "$STAGING_DIR" -type d -exec chmod 755 {} +
find "$STAGING_DIR" -type f -exec chmod 644 {} +
chmod 755 "$STAGING_DIR/DEBIAN/postinst" "$STAGING_DIR/DEBIAN/postrm"
chmod 755 "$STAGING_DIR/opt/cyberduck/bin/cyberduck"

dpkg-deb --build --root-owner-group "$STAGING_DIR" "$DEB_FILE"

cp "$DEB_FILE" "$DIST_DIR/cyberduck_latest_amd64.deb"

echo ""
echo "=========================================================="
echo "SUCCESS! Created package:"
echo "  $DEB_FILE"
echo "  $DIST_DIR/cyberduck_latest_amd64.deb"
echo ""
echo "Package size: $(du -h "$DEB_FILE" | cut -f1)"
echo "To install on any Ubuntu/Debian system:"
echo "  sudo dpkg -i $DEB_FILE"
echo "  sudo apt-get install -f   # (if any dependencies missing)"
echo "=========================================================="

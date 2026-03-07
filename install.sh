#!/bin/bash
# Nebula Files - Install Script
set -e

INSTALL_DIR="$HOME/.local/share/nebula-files"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

echo "Installing Nebula Files..."

# Remove old versions
rm -rf "$HOME/.local/share/nova-files" 2>/dev/null
rm -f "$HOME/.local/bin/nova-files" 2>/dev/null
rm -f "$DESKTOP_DIR/nova-files.desktop" 2>/dev/null

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/src/nebula-files.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/src/nebula-files-win11.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/src/nebula-files-launcher.py" "$INSTALL_DIR/"

cat > "$BIN_DIR/nebula-files" << 'EOF'
#!/bin/bash
cd "$HOME/.local/share/nebula-files"
exec python3 nebula-files-launcher.py "$@"
EOF
chmod +x "$BIN_DIR/nebula-files"

cp "$SCRIPT_DIR/data/icons/hicolor/scalable/apps/org.nebulaprojects.files.svg" "$ICON_DIR/"

cat > "$DESKTOP_DIR/org.nebulaprojects.files.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Nebula Files
Comment=Modern File Manager
Exec=$BIN_DIR/nebula-files
Icon=org.nebulaprojects.files
Categories=System;FileManager;Utility;
Terminal=false
StartupNotify=true
MimeType=inode/directory;
EOF

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "✓ Nebula Files installed!"
echo "  Launch from app menu or run: nebula-files"

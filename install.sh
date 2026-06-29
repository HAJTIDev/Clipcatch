#!/usr/bin/env bash
# ClipCatch installer for Fedora
# Sets up the tray app + autostart

set -e
INSTALL_DIR="$HOME/.local/share/clipcatch"
BIN_DIR="$HOME/.local/bin"
AUTOSTART_DIR="$HOME/.config/autostart"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing Python dependencies..."
pip install --user pystray pynput Pillow 2>/dev/null || \
pip3 install --user pystray pynput Pillow

echo "==> Installing ClipCatch..."
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/clipcatch.py" "$INSTALL_DIR/clipcatch.py"
chmod +x "$INSTALL_DIR/clipcatch.py"

# Create launcher script
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/clipcatch" << EOF
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/clipcatch.py" "\$@"
EOF
chmod +x "$BIN_DIR/clipcatch"

# Desktop entry for autostart
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/clipcatch.desktop" << EOF
[Desktop Entry]
Type=Application
Name=ClipCatch
Comment=OBS Replay Buffer clip saver
Exec=$BIN_DIR/clipcatch
Icon=media-record
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

echo ""
echo "✅ ClipCatch installed!"
echo ""
echo "   Run now:     clipcatch"
echo "   Autostart:   already set up — will start on login"
echo ""
echo "📋 OBS Setup required:"
echo "   1. Open OBS → Tools → WebSocket Server Settings"
echo "   2. Enable WebSocket Server (port 4455)"
echo "   3. Set a password (optional but recommended)"
echo "   4. Go to Settings → Output → Replay Buffer"
echo "      Enable replay buffer, set duration (e.g. 30s)"
echo "   5. Update ~/.config/clipcatch/config.json with your password"
echo ""
echo "🎮 Default hotkey: Ctrl+Shift+S"
echo "   (Change in ~/.config/clipcatch/config.json)"

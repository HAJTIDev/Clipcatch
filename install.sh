#!/usr/bin/env bash
# ClipCatch installer — auto-detects distro
# Supports: Fedora, Ubuntu, Debian, Mint, Arch, Manjaro, openSUSE, NixOS

set -e

INSTALL_DIR="$HOME/.local/share/clipcatch"
BIN_DIR="$HOME/.local/bin"
AUTOSTART_DIR="$HOME/.config/autostart"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Detect distro ─────────────────────────────────────────────────────────────

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_ID="${ID,,}"           # lowercase: fedora, ubuntu, arch, ...
    DISTRO_LIKE="${ID_LIKE,,}"    # e.g. "rhel fedora", "debian", etc.
else
    DISTRO_ID="unknown"
    DISTRO_LIKE=""
fi

echo "==> Detected distro: ${PRETTY_NAME:-$DISTRO_ID}"

# ── Helper: check if a command exists ─────────────────────────────────────────

has() { command -v "$1" &>/dev/null; }

# ── Install system dependencies ───────────────────────────────────────────────

install_sys_deps() {
    local obs_pkg="obs-studio"
    local notify_pkg=""
    local python_pkg=""

    # Fedora / RHEL / CentOS family
    if [[ "$DISTRO_ID" == "fedora" || "$DISTRO_LIKE" == *"fedora"* || "$DISTRO_LIKE" == *"rhel"* ]]; then
        notify_pkg="libnotify"
        python_pkg="python3-pip"
        echo "==> Installing system deps via dnf..."
        sudo dnf install -y "$obs_pkg" "$notify_pkg" "$python_pkg" || true

    # Ubuntu / Debian / Mint / Pop!_OS family
    elif [[ "$DISTRO_ID" == "ubuntu" || "$DISTRO_ID" == "debian" || "$DISTRO_ID" == "linuxmint" \
         || "$DISTRO_LIKE" == *"ubuntu"* || "$DISTRO_LIKE" == *"debian"* ]]; then
        notify_pkg="libnotify-bin"
        python_pkg="python3-pip"
        echo "==> Installing system deps via apt..."
        sudo apt-get update -qq
        sudo apt-get install -y "$obs_pkg" "$notify_pkg" "$python_pkg" || true

    # Arch / Manjaro / EndeavourOS family
    elif [[ "$DISTRO_ID" == "arch" || "$DISTRO_ID" == "manjaro" || "$DISTRO_ID" == "endeavouros" \
         || "$DISTRO_LIKE" == *"arch"* ]]; then
        notify_pkg="libnotify"
        python_pkg="python-pip"
        echo "==> Installing system deps via pacman..."
        sudo pacman -Sy --noconfirm "$obs_pkg" "$notify_pkg" "$python_pkg" || true

    # openSUSE family
    elif [[ "$DISTRO_ID" == "opensuse"* || "$DISTRO_ID" == "sles" || "$DISTRO_LIKE" == *"suse"* ]]; then
        notify_pkg="libnotify-tools"
        python_pkg="python3-pip"
        echo "==> Installing system deps via zypper..."
        sudo zypper install -y "$obs_pkg" "$notify_pkg" "$python_pkg" || true

    # NixOS — can't install normally, just warn
    elif [[ "$DISTRO_ID" == "nixos" ]]; then
        echo "⚠️  NixOS detected — skipping system package install."
        echo "   Make sure obs-studio and libnotify are in your environment:"
        echo "   nix-shell -p obs-studio libnotify python3 python3Packages.pip"
        echo ""

    else
        echo "⚠️  Unknown distro '$DISTRO_ID' — skipping system package install."
        echo "   Please manually install: obs-studio, libnotify, python3-pip"
        echo ""
    fi
}

# ── Detect OBS path (handles Flatpak / Snap / native) ─────────────────────────

detect_obs_path() {
    if has obs; then
        echo "$(command -v obs)"
    elif has flatpak && flatpak list --app 2>/dev/null | grep -q "com.obsproject.Studio"; then
        echo "flatpak"
    elif [ -f /snap/bin/obs ]; then
        echo "/snap/bin/obs"
    else
        echo "/usr/bin/obs"  # fallback default
    fi
}

# ── Fix OBS path in config if using Flatpak ───────────────────────────────────

patch_obs_path_if_flatpak() {
    local obs_path="$1"
    local config="$HOME/.config/clipcatch/config.json"

    if [[ "$obs_path" == "flatpak" ]]; then
        echo "ℹ️  OBS is installed as Flatpak."
        echo "   Setting obs_path to flatpak run command in config..."
        mkdir -p "$(dirname "$config")"
        # write/patch the config with flatpak path if it doesn't exist yet
        if [ ! -f "$config" ]; then
            cat > "$config" << EOF
{
  "obs_host": "localhost",
  "obs_port": 4455,
  "obs_password": "",
  "clips_dir": "${HOME}/Videos/Clips",
  "replay_duration": 30,
  "hotkey": "<alt>+s",
  "auto_start_obs": false,
  "obs_path": "flatpak run com.obsproject.Studio"
}
EOF
        fi
    fi
}

# ── Check if user is in 'input' group (needed for Wayland hotkeys) ────────────

check_input_group() {
    if groups "$USER" | grep -qw "input"; then
        echo "✅ User is already in 'input' group (Wayland hotkeys OK)"
    else
        echo "⚠️  Wayland hotkey note: your user is NOT in the 'input' group."
        read -rp "   Add yourself to 'input' group now? (requires sudo) [y/N] " answer
        if [[ "${answer,,}" == "y" ]]; then
            sudo usermod -aG input "$USER"
            echo "   ✅ Added! You'll need to log out and back in for it to take effect."
        else
            echo "   Skipped. You can do it later with: sudo usermod -aG input \$USER"
            echo "   Or set the hotkey via KDE/GNOME System Settings instead."
        fi
    fi
}

# ── Install Python packages ───────────────────────────────────────────────────

install_python_deps() {
    echo "==> Installing Python dependencies..."
    # try pip first, fallback to pip3, then pipx as last resort
    if has pip3; then
        pip3 install --user pystray pynput Pillow
    elif has pip; then
        pip install --user pystray pynput Pillow
    else
        echo "❌ pip not found! Install python3-pip for your distro first."
        exit 1
    fi
}

# ── Main install ──────────────────────────────────────────────────────────────

install_sys_deps

OBS_PATH="$(detect_obs_path)"
echo "==> OBS found at: ${OBS_PATH}"

install_python_deps

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

# Patch config for Flatpak OBS
patch_obs_path_if_flatpak "$OBS_PATH"

# Check Wayland input group
echo ""
check_input_group

# Make sure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "⚠️  $BIN_DIR is not in your PATH."
    echo "   Add this to your ~/.bashrc or ~/.zshrc:"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

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
echo "🎮 Default hotkey: Alt+S"
echo "   (Change in ~/.config/clipcatch/config.json)"
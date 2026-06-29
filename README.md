# ClipCatch 🎬

A lightweight system tray app for Linux that saves gameplay clips using OBS's replay buffer.  
Think Shadowplay/Medal but free, open, and Linux-native.

## How it works

ClipCatch connects to OBS via WebSocket and controls the **replay buffer** — OBS keeps the last N seconds of your screen recorded in memory. When you press the hotkey, it tells OBS to save those seconds as a clip file.

```
[Your screen] → [OBS replay buffer (last 30s)] → [Alt+S] → [clip saved to ~/Videos/Clips]
```

---

## Distro support

| Distro | Status | Package manager used |
|--------|--------|----------------------|
| Fedora / RHEL | ✅ | `dnf` |
| Ubuntu / Debian / Mint | ✅ | `apt` |
| Arch / Manjaro / EndeavourOS | ✅ | `pacman` |
| openSUSE | ✅ | `zypper` |
| NixOS | ⚠️ | manual (see below) |
| Other | ⚠️ | manual |

The installer auto-detects your distro and uses the right package manager. It also handles native, Flatpak, and Snap installs of OBS automatically.

---

## Requirements

- **Python 3.10+**
- **OBS Studio** (native, Flatpak, or Snap — all supported)
- `pystray`, `pynput`, `Pillow` — installed automatically by `install.sh`
- `libnotify` — installed automatically for desktop notifications

---

## Install

```bash
git clone https://github.com/Cloodowy/clipcatch
cd clipcatch
chmod +x install.sh
./install.sh
```

The installer will:
- detect your distro and install system dependencies
- install Python packages via pip
- detect whether OBS is native / Flatpak / Snap
- set up a `clipcatch` command in `~/.local/bin`
- add ClipCatch to autostart
- ask if you want to be added to the `input` group (needed for Wayland hotkeys)

---

## OBS Setup (one time)

1. Open OBS
2. **Tools → WebSocket Server Settings**
   - ✅ Enable WebSocket Server
   - Port: `4455`
   - Set a password (optional but recommended)
3. **Settings → Output → Replay Buffer**
   - ✅ Enable Replay Buffer
   - Maximum Replay Time: `30` seconds (or however long you want)
4. **Settings → Output → Recording**
   - Set output path to `~/Videos/Clips` (matches ClipCatch default)

---

## Config

Config file lives at `~/.config/clipcatch/config.json` and is created automatically on first run:

```json
{
  "obs_host": "localhost",
  "obs_port": 4455,
  "obs_password": "your_password_here",
  "clips_dir": "/home/you/Videos/Clips",
  "replay_duration": 30,
  "hotkey": "<alt>+s",
  "auto_start_obs": false,
  "obs_path": "/usr/bin/obs"
}
```

| Key | Description |
|-----|-------------|
| `obs_password` | WebSocket password (leave `""` if none set) |
| `clips_dir` | Where OBS saves clips (must match OBS output path) |
| `replay_duration` | Reminder only — set actual duration in OBS |
| `hotkey` | pynput format: `<alt>+s`, `<ctrl>+<shift>+s`, `<f9>`, etc. |
| `auto_start_obs` | If `true`, launches OBS automatically on startup |
| `obs_path` | Path to OBS binary (auto-detected by installer) |

> **Flatpak OBS:** the installer sets `obs_path` to `flatpak run com.obsproject.Studio` automatically.

---

## Tray menu

| Option | What it does |
|--------|-------------|
| 💾 Save Clip | Save the last N seconds right now |
| Connect to OBS | Connect to a running OBS instance |
| Disconnect | Stop controlling OBS |
| Launch OBS + Connect | Start OBS then auto-connect |
| ⚙ Open Config | Open config.json in your default editor |
| Quit | Exit ClipCatch |

---

## Tray icon

| Color | Meaning |
|-------|---------|
| 🔴 Red, pause bars | Not connected to OBS |
| 🟢 Green, white dot | Connected and buffering |

---

## Hotkeys on Wayland

Global hotkeys via `pynput` require your user to be in the `input` group. The installer will ask you about this automatically, or you can do it manually:

```bash
sudo usermod -aG input $USER
# log out and back in for it to take effect
```

**Alternative (no input group needed):** set the hotkey in your desktop environment instead:
- **KDE:** System Settings → Shortcuts → Custom Shortcuts → add command `clipcatch`
- **GNOME:** Settings → Keyboard → Custom Shortcuts → add command `clipcatch`

> On X11 global hotkeys work without any extra setup.

---

## Running OBS in the background

Launch OBS minimized to tray with the replay buffer already started:

```bash
obs --minimize-to-tray --startreplaybuffer
```

Or set `"auto_start_obs": true` in the config and ClipCatch will handle it automatically on startup.

---

## NixOS

The installer skips package management on NixOS. Set up a shell with the required packages first:

```bash
nix-shell -p obs-studio libnotify python3 python3Packages.pip
./install.sh
```

---

## License

MIT
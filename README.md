# ClipCatch 🎬

A lightweight system tray app for Fedora that saves gameplay clips using OBS's replay buffer.  
Think Shadowplay/Medal but free, open, and Linux-native.

## How it works

ClipCatch connects to OBS via WebSocket and controls the **replay buffer** — OBS keeps the last N seconds of your screen recorded in memory. When you press the hotkey, it tells OBS to save those seconds as a clip file.

```
[Your screen] → [OBS replay buffer (last 30s)] → [Ctrl+Shift+S] → [clip saved to ~/Videos/Clips]
```

---

## Requirements

- **OBS Studio** (`sudo dnf install obs-studio`)
- **Python 3.10+** (already on Fedora)
- `pystray`, `pynput`, `Pillow` (installed by install.sh)
- `libnotify` for desktop notifications (`sudo dnf install libnotify`)

---

## Install

```bash
chmod +x install.sh
./install.sh
```

---

## OBS Setup (one time)

1. Open OBS
2. **Tools → WebSocket Server Settings**
   - ✅ Enable WebSocket Server
   - Port: `4455`
   - Set a password (optional)
3. **Settings → Output → Replay Buffer**
   - ✅ Enable Replay Buffer
   - Maximum Replay Time: `30` seconds (or however long you want)
4. **Settings → Output → Recording**
   - Set output path to `~/Videos/Clips` (matches ClipCatch default)

---

## Config

Config file lives at `~/.config/clipcatch/config.json`:

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
| `hotkey` | pynput format: `<ctrl>+<shift>+s`, `<alt>+s`, `<f9>`, etc. |
| `auto_start_obs` | If `true`, launches OBS automatically on startup |
| `obs_path` | Path to OBS binary |

---

## Tray Menu

| Option | What it does |
|--------|-------------|
| 💾 Save Clip | Save the last N seconds right now |
| Connect to OBS | Connect to running OBS instance |
| Disconnect | Stop controlling OBS |
| Launch OBS + Connect | Start OBS then auto-connect |
| ⚙ Open Config | Open config.json in your editor |
| Quit | Exit ClipCatch |

---

## Tray Icon Colors

| Color | Meaning |
|-------|---------|
| 🔴 Red (pause icon) | Not connected to OBS |
| 🟢 Green (dot icon) | Connected and buffering |

---

## Hotkey note (Wayland/KDE)

On KDE Wayland, global hotkeys via `pynput` require your user to be in the `input` group:

```bash
sudo usermod -aG input $USER
# then log out and back in
```

Alternatively you can set up the hotkey in **KDE System Settings → Shortcuts → Custom Shortcuts** and point it to:
```bash
clipcatch --save
```
(future feature)

---

## Running without OBS visible

Launch OBS minimized to tray with replay buffer auto-started:

```bash
obs --minimize-to-tray --startreplaybuffer
```

Or set `"auto_start_obs": true` in the config and ClipCatch will do it for you.

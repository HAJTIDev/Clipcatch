#!/usr/bin/env python3
"""
ClipCatch - Linux clip saver tray app
Controls OBS replay buffer via WebSocket
"""

import json
import os
import sys
import time
import threading
import subprocess
import base64
import hashlib
import struct
import socket
import ssl
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw
import pystray

# ─── Config ───────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".config" / "clipcatch" / "config.json"
DEFAULT_CONFIG = {
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_password": "",
    "clips_dir": str(Path.home() / "Videos" / "Clips"),
    "replay_duration": 30,
    "hotkey": "<alt>+s",
    "auto_start_obs": False,
    "obs_path": "/usr/bin/obs",
}

# ─── Simple OBS WebSocket 5.x client ──────────────────────────────────────────

class OBSClient:
    """Minimal OBS WebSocket 5.x client (no external deps)"""

    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.ws = None
        self._msg_id = 1
        self._lock = threading.Lock()

    def _ws_connect(self):
        """Open a raw WebSocket connection"""
        sock = socket.create_connection((self.host, self.port), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(handshake.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += sock.recv(4096)
        return sock

    def _ws_send(self, sock, data: dict):
        payload = json.dumps(data).encode("utf-8")
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", 0x81, 0x80 | length)
        elif length < 65536:
            header = struct.pack("!BBH", 0x81, 0xFE, length)
        else:
            header = struct.pack("!BBQ", 0x81, 0xFF, length)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        sock.sendall(header + mask + masked)

    def _ws_recv(self, sock) -> dict:
        def recv_exact(n):
            buf = b""
            while len(buf) < n:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError("WebSocket closed")
                buf += chunk
            return buf

        header = recv_exact(2)
        opcode = header[0] & 0x0F
        masked = (header[1] & 0x80) != 0
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", recv_exact(8))[0]
        if masked:
            mask = recv_exact(4)
        data = recv_exact(length)
        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 8:  # close
            raise ConnectionError("WebSocket closed by server")
        return json.loads(data.decode("utf-8"))

    def connect(self) -> tuple[bool, str]:
        try:
            self.ws = self._ws_connect()

            # receive Hello
            hello = self._ws_recv(self.ws)
            if hello.get("op") != 0:
                return False, "Expected Hello (op=0)"

            auth_required = hello.get("d", {}).get("authentication")

            identify_data = {
                "rpcVersion": 1,
                "eventSubscriptions": 0,
            }

            if auth_required and self.password:
                challenge = auth_required["challenge"]
                salt = auth_required["salt"]
                secret = base64.b64encode(
                    hashlib.sha256((self.password + salt).encode()).digest()
                ).decode()
                auth_str = base64.b64encode(
                    hashlib.sha256((secret + challenge).encode()).digest()
                ).decode()
                identify_data["authentication"] = auth_str

            self._ws_send(self.ws, {"op": 1, "d": identify_data})

            identified = self._ws_recv(self.ws)
            if identified.get("op") != 2:
                return False, f"Auth failed: {identified}"

            return True, "Connected"
        except Exception as e:
            return False, str(e)

    def request(self, req_type: str, data: dict = None) -> dict:
        if not self.ws:
            raise ConnectionError("Not connected")
        with self._lock:
            msg_id = str(self._msg_id)
            self._msg_id += 1
            payload = {
                "op": 6,
                "d": {
                    "requestType": req_type,
                    "requestId": msg_id,
                    "requestData": data or {},
                },
            }
            self._ws_send(self.ws, payload)
            # read until we get the response for our request
            for _ in range(20):
                resp = self._ws_recv(self.ws)
                if resp.get("op") == 7 and resp["d"].get("requestId") == msg_id:
                    return resp["d"]
            raise TimeoutError("No response from OBS")

    def disconnect(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None


# ─── Config helpers ────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        # fill in any missing keys
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ─── Tray icon drawing ─────────────────────────────────────────────────────────

def make_icon(connected: bool, buffering: bool) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # background circle
    bg = (34, 197, 94) if connected else (239, 68, 68)  # green / red
    draw.ellipse([4, 4, 60, 60], fill=bg)

    # small record dot when buffering
    if buffering:
        draw.ellipse([22, 22, 42, 42], fill=(255, 255, 255))
    else:
        # pause bars
        draw.rectangle([20, 20, 28, 44], fill=(255, 255, 255))
        draw.rectangle([36, 20, 44, 44], fill=(255, 255, 255))

    return img


# ─── Main App ──────────────────────────────────────────────────────────────────

class ClipCatch:
    def __init__(self):
        self.cfg = load_config()
        self.obs: OBSClient | None = None
        self.connected = False
        self.buffering = False
        self.status_msg = "Disconnected"
        self.icon: pystray.Icon | None = None
        self._hotkey_thread: threading.Thread | None = None
        self._connect_thread: threading.Thread | None = None

    # ── OBS connection ──────────────────────────────────────────────────────

    def _connect_obs(self):
        self.obs = OBSClient(
            self.cfg["obs_host"],
            self.cfg["obs_port"],
            self.cfg["obs_password"],
        )
        ok, msg = self.obs.connect()
        if ok:
            self.connected = True
            self.status_msg = "Connected to OBS"
            self._update_icon()
            # start replay buffer if not running
            try:
                status = self.obs.request("GetReplayBufferStatus")
                if not status.get("responseData", {}).get("outputActive", False):
                    self.obs.request("StartReplayBuffer")
                    self.buffering = True
                    self.status_msg = "Buffering…"
                else:
                    self.buffering = True
                    self.status_msg = "Buffering…"
                self._update_icon()
            except Exception as e:
                self.status_msg = f"Buffer error: {e}"
        else:
            self.connected = False
            self.status_msg = f"OBS connect failed: {msg}"
            self._update_icon()

    def connect_to_obs(self):
        if self._connect_thread and self._connect_thread.is_alive():
            return
        self._connect_thread = threading.Thread(target=self._connect_obs, daemon=True)
        self._connect_thread.start()

    def disconnect_from_obs(self):
        if self.obs:
            try:
                if self.buffering:
                    self.obs.request("StopReplayBuffer")
            except Exception:
                pass
            self.obs.disconnect()
        self.connected = False
        self.buffering = False
        self.status_msg = "Disconnected"
        self._update_icon()

    # ── Clip saving ─────────────────────────────────────────────────────────

    def save_clip(self, icon=None, item=None):
        if not self.connected or not self.buffering:
            self._notify("ClipCatch", "Not connected to OBS or buffer not running")
            return
        try:
            result = self.obs.request("SaveReplayBuffer")
            status = result.get("requestStatus", {})
            if status.get("result", False):
                self._notify("ClipCatch ✂️", "Clip saved!")
            else:
                err = status.get("comment", "Unknown error")
                self._notify("ClipCatch", f"Save failed: {err}")
        except Exception as e:
            self._notify("ClipCatch", f"Error: {e}")

    # ── Hotkey listener ─────────────────────────────────────────────────────

    def _start_hotkey_listener(self):
        """Listen for the save hotkey using pynput"""
        try:
            from pynput import keyboard

            hotkey_str = self.cfg.get("hotkey", "<ctrl>+<shift>+s")

            def on_activate():
                self.save_clip()

            listener = keyboard.GlobalHotKeys({hotkey_str: on_activate})
            listener.start()
            listener.join()
        except ImportError:
            pass  # pynput not installed, hotkey disabled
        except Exception:
            pass

    # ── OBS auto-start ──────────────────────────────────────────────────────

    def _launch_obs(self):
        obs_path = self.cfg.get("obs_path", "/usr/bin/obs")
        try:
            subprocess.Popen(
                [obs_path, "--minimize-to-tray", "--startreplaybuffer"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(4)
            self.connect_to_obs()
        except FileNotFoundError:
            self.status_msg = f"OBS not found at {obs_path}"
            self._update_icon()

    # ── Notification ────────────────────────────────────────────────────────

    def _notify(self, title: str, msg: str):
        try:
            subprocess.Popen(
                ["notify-send", "-a", "ClipCatch", title, msg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass

    # ── Tray icon ───────────────────────────────────────────────────────────

    def _update_icon(self):
        if self.icon:
            self.icon.icon = make_icon(self.connected, self.buffering)
            self.icon.title = f"ClipCatch — {self.status_msg}"

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                lambda _: f"● {self.status_msg}",
                lambda: None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("💾 Save Clip  (Alt+S)", self.save_clip),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Connect to OBS",
                lambda icon, item: self.connect_to_obs(),
                enabled=lambda item: not self.connected,
            ),
            pystray.MenuItem(
                "Disconnect",
                lambda icon, item: self.disconnect_from_obs(),
                enabled=lambda item: self.connected,
            ),
            pystray.MenuItem(
                "Launch OBS + Connect",
                lambda icon, item: threading.Thread(
                    target=self._launch_obs, daemon=True
                ).start(),
                enabled=lambda item: not self.connected,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙ Open Config", self._open_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _open_config(self, icon=None, item=None):
        save_config(self.cfg)  # ensure file exists
        try:
            subprocess.Popen(["xdg-open", str(CONFIG_PATH)])
        except FileNotFoundError:
            subprocess.Popen(["kate", str(CONFIG_PATH)])

    def _quit(self, icon=None, item=None):
        self.disconnect_from_obs()
        if self.icon:
            self.icon.stop()

    # ── Run ─────────────────────────────────────────────────────────────────

    def run(self):
        # ensure clips dir exists
        Path(self.cfg["clips_dir"]).mkdir(parents=True, exist_ok=True)
        save_config(self.cfg)

        # start hotkey listener
        self._hotkey_thread = threading.Thread(
            target=self._start_hotkey_listener, daemon=True
        )
        self._hotkey_thread.start()

        # auto-connect or auto-launch
        if self.cfg.get("auto_start_obs"):
            threading.Thread(target=self._launch_obs, daemon=True).start()
        else:
            self.connect_to_obs()

        # build and run tray icon
        self.icon = pystray.Icon(
            "clipcatch",
            make_icon(False, False),
            f"ClipCatch — {self.status_msg}",
            menu=self._build_menu(),
        )
        self.icon.run()


if __name__ == "__main__":
    app = ClipCatch()
    app.run()

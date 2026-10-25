"""Tiny socket client used by the Super+F shortcut; deliberately imports no GTK."""

import socket
import subprocess
import sys
import time

from .config import SOCKET_PATH


def _connect(message: bytes = b"") -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(str(SOCKET_PATH))
            if message:
                s.sendall(message)
        return True
    except (FileNotFoundError, ConnectionRefusedError):
        return False


def running() -> bool:
    return _connect()


def stop() -> int:
    """Ask a running daemon to quit, waiting until it has."""
    if _connect(b"quit\n"):
        for _ in range(30):
            time.sleep(0.1)
            if not running():
                break
    return 0


def trigger() -> int:
    """Ask the daemon to look up the selection, starting it first if needed."""
    if _connect(b"lookup\n"):
        return 0
    subprocess.Popen(
        [sys.executable, "-m", "french_lookup", "daemon"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        time.sleep(0.1)
        if _connect(b"lookup\n"):
            return 0
    print("french-lookup: daemon did not start", file=sys.stderr)
    return 1

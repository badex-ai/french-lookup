import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home()
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "french-lookup" / "config.toml"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local" / "share")) / "french-lookup"
SOCKET_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/french-lookup-{os.getuid()}")) / "french-lookup.sock"


@dataclass
class Config:
    model: str = "sonnet"
    timeout_seconds: int = 30
    max_chars: int = 300
    batch_size: int = 200
    claude_path: str = ""


def load() -> Config:
    cfg = Config()
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as f:
            data = tomllib.load(f)
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
    return cfg

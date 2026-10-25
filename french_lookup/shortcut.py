"""Register Super+F as a GNOME custom keyboard shortcut."""

from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio

SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
KEY_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/french-lookup/"
BINDING = "<Super>f"
COMMAND = f"{Path.home() / '.local/bin/french-lookup'} trigger"


def register(command: str = COMMAND, binding: str = BINDING):
    settings = Gio.Settings.new(SCHEMA)
    paths = settings.get_strv("custom-keybindings")
    if KEY_PATH not in paths:
        settings.set_strv("custom-keybindings", paths + [KEY_PATH])
    kb = Gio.Settings.new_with_path(SCHEMA + ".custom-keybinding", KEY_PATH)
    kb.set_string("name", "French lookup")
    kb.set_string("command", command)
    kb.set_string("binding", binding)
    Gio.Settings.sync()


def unregister():
    settings = Gio.Settings.new(SCHEMA)
    paths = settings.get_strv("custom-keybindings")
    if KEY_PATH in paths:
        settings.set_strv("custom-keybindings", [p for p in paths if p != KEY_PATH])
    kb = Gio.Settings.new_with_path(SCHEMA + ".custom-keybinding", KEY_PATH)
    for key in ("name", "command", "binding"):
        kb.reset(key)
    Gio.Settings.sync()

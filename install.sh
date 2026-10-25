#!/bin/sh
# Install french-lookup for the current user. Safe to re-run (upgrades in place).
set -eu

SRC=$(cd "$(dirname "$0")" && pwd)
LIB="$HOME/.local/lib/french-lookup"
BIN="$HOME/.local/bin/french-lookup"
AUTOSTART="$HOME/.config/autostart/french-lookup.desktop"

if [ "${XDG_SESSION_TYPE:-}" != "x11" ]; then
    echo "warning: this is a '${XDG_SESSION_TYPE:-unknown}' session; french-lookup is built for X11." >&2
fi
if ! command -v claude >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/claude" ]; then
    echo "error: Claude Code ('claude') not found. Install it and log in first." >&2
    exit 1
fi
if ! /usr/bin/python3 -c 'import gi; gi.require_version("AyatanaAppIndicator3", "0.1")' 2>/dev/null; then
    if [ -t 0 ]; then
        echo "Installing tray icon support (asks for your password)..."
        sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1 ||
            echo "warning: tray icon unavailable; lookups still work." >&2
    else
        echo "note: for the tray icon, run: sudo apt install gir1.2-ayatanaappindicator3-0.1" >&2
    fi
fi

PYTHONPATH="$SRC" /usr/bin/python3 -m french_lookup stop

rm -rf "$LIB"
mkdir -p "$LIB" "$(dirname "$BIN")" "$(dirname "$AUTOSTART")"
cp -r "$SRC/french_lookup" "$LIB/"
find "$LIB" -name __pycache__ -prune -exec rm -rf {} +

cat > "$BIN" <<EOF
#!/bin/sh
PYTHONPATH="$LIB" exec /usr/bin/python3 -m french_lookup "\$@"
EOF
chmod +x "$BIN"

cat > "$AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=French lookup
Comment=Select French text and press Super+F
Exec=$BIN daemon
Icon=accessories-dictionary
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF

"$BIN" register-shortcut
setsid "$BIN" daemon >/dev/null 2>&1 < /dev/null &

echo "Installed. Select French text anywhere and press Super+F."
echo "Cards are saved in ${XDG_DATA_HOME:-$HOME/.local/share}/french-lookup/batches/ (200 cards per CSV)"

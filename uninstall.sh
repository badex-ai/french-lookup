#!/bin/sh
# Remove french-lookup. Your saved cards are kept unless you pass --purge.
set -eu

LIB="$HOME/.local/lib/french-lookup"
BIN="$HOME/.local/bin/french-lookup"
AUTOSTART="$HOME/.config/autostart/french-lookup.desktop"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/french-lookup"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/french-lookup"

if [ -x "$BIN" ]; then
    "$BIN" stop || true
    "$BIN" unregister-shortcut || true
fi
rm -rf "$LIB" "$BIN" "$AUTOSTART"

if [ "${1:-}" = "--purge" ]; then
    rm -rf "$DATA" "$CONFIG"
    echo "Uninstalled, including saved cards and config."
else
    echo "Uninstalled. Your cards are still in $DATA (use --purge to delete them)."
fi

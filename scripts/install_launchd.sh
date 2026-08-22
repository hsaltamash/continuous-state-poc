#!/bin/zsh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$ROOT/launchd/com.demo.continuous-state-capture.plist.template"
TARGET="$HOME/Library/LaunchAgents/com.demo.continuous-state-capture.plist"
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|__ROOT__|$ROOT|g" "$TEMPLATE" > "$TARGET"
launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$TARGET"
echo "Installed: $TARGET"
echo "Runs every 300 seconds and once immediately at load."

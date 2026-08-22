#!/bin/zsh
set -eu
TARGET="$HOME/Library/LaunchAgents/com.demo.continuous-state-capture.plist"
launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
rm -f "$TARGET"
echo "Removed scheduled capture job."

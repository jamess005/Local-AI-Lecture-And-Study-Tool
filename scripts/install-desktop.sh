#!/bin/bash
# Install the launcher. The icon is a stock freedesktop theme name, so there is
# nothing to copy - the desktop resolves it from the active icon theme, and the
# app looks up the same name for its window icon so the two always agree.
set -euo pipefail
cd "$(dirname "$0")/.."
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
cp "voiceagent.desktop" "$APPS/"
update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "installed voiceagent.desktop"
echo "if the panel still shows an old icon, restart your shell (Cinnamon: Ctrl+Alt+Esc)"

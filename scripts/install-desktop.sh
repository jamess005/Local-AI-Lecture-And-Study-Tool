#!/bin/bash
# Install the launcher and its icon into the user's desktop environment.
#
# The non-obvious part is index.theme. A directory under ~/.local/share/icons
# is only treated as an icon theme if it contains one; without it the whole
# tree is ignored and the launcher silently falls back to a generic icon, no
# matter how many correctly-named PNGs are in there. Nothing warns you.
set -euo pipefail
cd "$(dirname "$0")/.."

ICONS="$HOME/.local/share/icons/hicolor"
APPS="$HOME/.local/share/applications"
SIZES=(16 24 32 48 64 128 256)

if [ ! -f "$ICONS/index.theme" ]; then
  mkdir -p "$ICONS"
  {
    printf '[Icon Theme]\nName=hicolor\nComment=Fallback icon theme\nDirectories='
    printf '%s,' "${SIZES[@]/%/x_/apps}" | sed 's/\([0-9]*\)x_/\1x\1/g'
    printf 'scalable/apps\n\n'
    for s in "${SIZES[@]}"; do
      printf '[%sx%s/apps]\nSize=%s\nContext=Applications\nType=Fixed\n\n' "$s" "$s" "$s"
    done
    printf '[scalable/apps]\nSize=48\nMinSize=8\nMaxSize=512\nContext=Applications\nType=Scalable\n'
  } > "$ICONS/index.theme"
  echo "wrote $ICONS/index.theme"
fi

for s in "${SIZES[@]}"; do
  if [ -f "assets/lecture-study-tool-$s.png" ]; then
    mkdir -p "$ICONS/${s}x${s}/apps"
    cp "assets/lecture-study-tool-$s.png" "$ICONS/${s}x${s}/apps/lecture-study-tool.png"
  fi
done
mkdir -p "$ICONS/scalable/apps"
cp "assets/lecture-study-tool.svg" "$ICONS/scalable/apps/lecture-study-tool.svg"

mkdir -p "$APPS"
cp "voiceagent.desktop" "$APPS/"

gtk-update-icon-cache -f -t "$ICONS" >/dev/null 2>&1 || true
update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "installed voiceagent.desktop and the lecture-study-tool icon"
echo "if the panel still shows the old icon, restart your shell (Cinnamon: Ctrl+Alt+Esc)"

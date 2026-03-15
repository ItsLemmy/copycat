#!/bin/bash
# Noctalia color generation hook — regenerate Copycat icon colors
# from the noctalia palette and apply them.
#
# Hook argument from noctalia:
#   $1 = theme (dark/light)
#
# Setup: In noctalia settings, set:
#   hooks.enabled = true
#   hooks.colorGeneration = "~/Development/misc/copycat/noctalia-hook.sh $1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/source"
BUILD_DIR="/tmp/copycat-noctalia"
THEME_NAME="Copycat-noctalia"

python3 "$SCRIPT_DIR/copycat-recolor.py" \
    --noctalia --flat \
    --name "$THEME_NAME" \
    --install --apply \
    "$SOURCE_DIR" "$BUILD_DIR" \
    > /dev/null 2>&1

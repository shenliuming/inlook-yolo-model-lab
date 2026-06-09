#!/usr/bin/env bash

set -e

echo "=== INLOOK Custom Voices Packager (Mac) ==="

VOICES_DIR="apps/yolo-api/runtime/content_lab/voices"
DESKTOP_DIR="$HOME/Desktop"
OUTPUT_ARCHIVE="$DESKTOP_DIR/inlook_voices_backup.tar.gz"

if [ -d "$VOICES_DIR" ] && [ "$(ls -A $VOICES_DIR)" ]; then
  echo "Found custom voices in $VOICES_DIR"
  echo "Packaging to $OUTPUT_ARCHIVE..."
  
  # Navigate to the parent directory to pack the 'voices' folder neatly
  cd "apps/yolo-api/runtime/content_lab"
  tar -czf "$OUTPUT_ARCHIVE" "voices"
  
  echo "Success! Packed custom voices to $OUTPUT_ARCHIVE"
  echo "You can transfer this archive to your Windows machine and extract it to the corresponding runtime directory."
else
  echo "No custom voices found in $VOICES_DIR, or directory is empty."
  echo "Nothing to pack."
fi

#!/usr/bin/env bash

set -e

echo "=== INLOOK Windows Migration Asset Preparation (Mac) ==="

# 1. Verify and clean MOSS-TTS models
echo ">> Checking MOSS-TTS models directory..."
MOSS_DIR="third_party/MOSS-TTS-Nano/models"
if [ -d "$MOSS_DIR" ]; then
  echo "Found MOSS_DIR: $MOSS_DIR"
  # Find and delete all files except README.md and .gitkeep
  find "$MOSS_DIR" -type f -not -name "README.md" -not -name ".gitkeep" -exec rm -f {} +
  echo "Cleaned MOSS model files. Only README.md and .gitkeep remain."
else
  echo "MOSS_DIR not found. Skipping cleanup."
fi

# 2. Check for CosyVoice Model
echo ">> Checking CosyVoice Model..."
# Assuming it might be outside the workspace as per previous checks
COSY_MAC_PATH="/Users/shen/models/inlook/pretrained_models/CosyVoice2-0.5B"
if [ -d "$COSY_MAC_PATH" ]; then
  echo "Found CosyVoice model at $COSY_MAC_PATH"
  echo "NOTE: This model is large. Windows side should download it externally."
else
  echo "CosyVoice model not found at expected path. Windows side must download it externally."
fi

# 3. Check for Custom Voices Library
echo ">> Checking Custom Voices Library..."
VOICES_DIR="apps/yolo-api/runtime/content_lab/voices"
if [ -d "$VOICES_DIR" ] && [ "$(ls -A $VOICES_DIR)" ]; then
  echo "Found Custom Voices Library at $VOICES_DIR"
  echo "You can use scripts/pack_voice_assets_mac.sh to package it."
else
  echo "No Custom Voices Library found to migrate."
fi

# 4. Check for Test Materials
echo ">> Checking Test Materials..."
TEST_VID="/Users/shen/Downloads/口播数字训练.mp4"
if [ -f "$TEST_VID" ]; then
  echo "Found test video at $TEST_VID"
  echo "NOTE: Remember to transfer this file to Windows manually if needed."
else
  echo "Test video not found. Skipping."
fi

# 5. Git Status Check
echo ">> Checking Git Status for anomalies..."
if git ls-files --error-unmatch .env.local >/dev/null 2>&1; then
  echo "WARNING: .env.local is currently tracked by Git! Please run 'git rm --cached .env.local' immediately."
else
  echo "Good: .env.local is NOT tracked by Git."
fi

echo ">> Checking for tracked large files (>20MB)..."
# Simplified check: identify files tracked by git over ~20MB
git ls-tree -r HEAD | awk '{print $4}' | while read f; do
  if [ -f "$f" ]; then
    size=$(wc -c <"$f" 2>/dev/null || echo 0)
    if [ "$size" -gt 20971520 ]; then
      echo "WARNING: Large file tracked by Git: $f ($((size/1024/1024))MB)"
    fi
  fi
done
echo "Asset preparation check complete."

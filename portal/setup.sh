#!/bin/bash
# Creates symlinks from platforms/ → src/content/docs/ so Starlight treats them as native docs.
# Also cleans up dangling symlinks from removed platforms.
cd "$(dirname "$0")"
mkdir -p src/content/docs

# ── Cleanup: remove symlinks whose target no longer exists ──
for link in src/content/docs/*/; do
  link="${link%/}"
  [ -L "$link" ] && [ ! -e "$link" ] && rm "$link" && echo "[cleanup] Removed dangling symlink: $link"
done

# ── Create/update symlinks for all valid platforms ──
for platform_dir in ../platforms/*/; do
  name=$(basename "$platform_dir")
  if [ -f "$platform_dir/platform.yaml" ]; then
    ln -sfn "../../../../platforms/$name" "src/content/docs/$name"
    echo "[ok] Symlink: src/content/docs/$name → platforms/$name"
  fi
done

#!/bin/bash
# Creates symlinks from platforms/ → src/content/docs/ so Starlight treats them as native docs
cd "$(dirname "$0")"
mkdir -p src/content/docs

for platform_dir in ../platforms/*/; do
  name=$(basename "$platform_dir")
  if [ -f "$platform_dir/platform.yaml" ]; then
    ln -sfn "../../../../platforms/$name" "src/content/docs/$name"
    echo "[ok] Symlink: src/content/docs/$name → platforms/$name"
  fi
done

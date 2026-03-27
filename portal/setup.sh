#!/bin/bash
# Creates symlinks from platforms/ → src/content/docs/ so Starlight treats them as native docs
cd "$(dirname "$0")"
mkdir -p src/content/docs
ln -sfn ../../../../platforms/fulano src/content/docs/fulano
echo "Symlink created: src/content/docs/fulano → platforms/fulano"

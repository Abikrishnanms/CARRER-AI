#!/bin/sh
set -e

# Install CPU-only PyTorch + sentence-transformers at runtime if not present
if ! python -c "import torch" 2>/dev/null; then
  echo "torch not found, installing CPU-only PyTorch..."
  for i in 1 2 3 4 5; do
    python -m pip install --no-cache-dir --timeout 120 --retries 5 --index-url https://download.pytorch.org/whl/cpu torch && break || \
      (echo "torch install attempt $i failed, retrying..." && sleep $((i*10)))
  done
else
  echo "torch already installed, skipping"
fi

if ! python -c "import sentence_transformers" 2>/dev/null; then
  echo "sentence-transformers not found, installing..."
  for i in 1 2 3 4 5; do
    python -m pip install --no-cache-dir --timeout 120 --retries 5 sentence-transformers && break || \
      (echo "sentence-transformers install attempt $i failed, retrying..." && sleep $((i*10)))
  done
else
  echo "sentence-transformers already installed, skipping"
fi

exec "$@"

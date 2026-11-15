#!/usr/bin/env bash
# Download the Kokoro-82M ONNX voice model (Apache-2.0) used for self-hosted interviewer speech.
set -euo pipefail
dest="${KOKORO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backend/models/kokoro}"
base="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
mkdir -p "$dest"
for file in kokoro-v1.0.onnx voices-v1.0.bin; do
  [[ -s "$dest/$file" ]] || curl --fail --location --silent --show-error -o "$dest/$file" "$base/$file"
done
echo "Kokoro model ready in $dest"

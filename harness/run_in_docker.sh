#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f BENCHMARK_BRIEF.md || ! -f fixtures/base.py || ! -f harness/Dockerfile ]]; then
  echo "Run this script from the project root." >&2
  exit 1
fi

docker build -t gone-for-good-harness -f harness/Dockerfile .
docker run --rm --network none -v "$PWD":/work -w /work gone-for-good-harness python -m harness.run "$@"

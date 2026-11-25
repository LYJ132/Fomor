#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PYTHONPATH=scripts/lib exec python3 -m unittest discover -s tests -v

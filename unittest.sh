#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREP_SCRIPT="$ROOT_DIR/prepenv.sh"
VENV_DIR="$ROOT_DIR/.venv_test"

print(){
    echo
    echo "==== $* ===="
}

if [ ! -f "$PREP_SCRIPT" ]; then
    echo "Expected $PREP_SCRIPT to exist."
    exit 1
fi

print "Preparing environment (this may install packages / postgresql)..."
# Run prepenv to ensure venv and dependencies are installed and postgres prepared
bash "$PREP_SCRIPT"

# Activate venv
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

print "Running unittest discovery under coverage"
coverage erase || true
rm -rf htmlcov || true
coverage run --source=morm -m unittest discover -s tests
coverage html

print "Unittest run complete; HTML report is in htmlcov/index.html"

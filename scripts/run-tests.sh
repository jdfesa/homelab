#!/bin/sh
# Local-only tests: no server access or provisioning actions.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python=${PYTHON:-python3}

printf '%s\n' '=== Shared repository tests ==='
"$python" -m unittest discover -s "$root/tests" -v

for module in "$root"/*/; do
    if [ -f "$module/README.md" ] && [ -d "$module/tests" ]; then
        printf '\n=== %s tests ===\n' "$(basename -- "$module")"
        "$python" -m unittest discover -s "$module/tests" -v
    fi
done

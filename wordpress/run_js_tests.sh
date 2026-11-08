#!/usr/bin/env bash
set -euo pipefail

PLUGINS=(
  wordpress/protohaven-airtable-grid
  wordpress/protohaven-class-ticker
  wordpress/protohaven-events
)

for d in "${PLUGINS[@]}"; do
  if [ ! -d "$d/node_modules" ]; then
    echo "Missing node_modules in $d. Run: pnpm install --dir $d" >&2
    exit 1
  fi
  echo "Running JS unit tests in $d"
  CI=1 pnpm --dir "$d" test:js
done

#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is not installed. Install: https://github.com/gitleaks/gitleaks" >&2
  exit 127
fi

gitleaks detect --source . --config .gitleaks.toml --redact --verbose "$@"

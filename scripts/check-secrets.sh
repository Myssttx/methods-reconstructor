#!/usr/bin/env bash
set -euo pipefail

secret_paths_regex='(^|/)(\.env|aayush_env\.txt|service-account-key\.json)$'
tracked_secret_paths="$(git ls-files | grep -E "$secret_paths_regex" || true)"
if [[ -n "$tracked_secret_paths" ]]; then
  echo "ERROR: secret-bearing files are tracked:"
  printf '%s\n' "$tracked_secret_paths"
  exit 1
fi

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks git --redact --no-banner
  echo "OK: gitleaks found no committed secrets."
  exit 0
fi

signature_regex='AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[0-9A-Za-z]{20,}|xox[baprs]-[0-9A-Za-z-]{10,}|sk-(live|proj)-[0-9A-Za-z_-]{16,}|-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----|"private_key"[[:space:]]*:'
signature_files="$(
  git grep -IlE "$signature_regex" -- \
    ':!scripts/check-secrets.sh' \
    ':!frontend/package-lock.json' \
    || true
)"
if [[ -n "$signature_files" ]]; then
  echo "ERROR: credential-like signatures found in tracked files:"
  printf '%s\n' "$signature_files"
  exit 1
fi

assignment_regex='(GOOGLE_API_KEY|ANTHROPIC_API_KEY|ELASTIC_API_KEY|SEMANTIC_SCHOLAR_API_KEY|PASSWORD|SECRET|TOKEN)[[:space:]]*=[[:space:]]*[^[:space:]#<${}]+'
assignment_files="$(
  git grep -IlE "$assignment_regex" -- \
    ':!.env.example' \
    ':!scripts/check-secrets.sh' \
    ':!frontend/package-lock.json' \
    || true
)"
if [[ -n "$assignment_files" ]]; then
  echo "ERROR: non-placeholder secret assignments found in tracked files:"
  printf '%s\n' "$assignment_files"
  exit 1
fi

echo "OK: no tracked secret files or common credential signatures found."

#!/usr/bin/env bash
# Simulates retrieval output from recollect (or any search tool).
# Each line is a vault-relative note path passed to memtag pack --stdin.
set -euo pipefail

cat <<'EOF'
deploy-api-production.md
deploy-api-staging.md
user-prefs.md
EOF
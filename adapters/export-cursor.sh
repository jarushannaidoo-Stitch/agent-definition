#!/usr/bin/env bash
# Compile pack skills -> Cursor (~/.cursor/skills) and portable (~/agents/skills).
# Skills for Codex live in ~/.agents/skills (export-codex.sh).
# Do NOT also write ~/.codex/skills - Codex loads both and shows duplicates.
# Flags: --check | --dry-run, --prune, --diff
# Logic lives in lib/agentpack.py (shared by every exporter).
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/agentpack.py" cursor "$@"

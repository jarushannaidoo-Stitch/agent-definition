#!/usr/bin/env bash
# Write or verify only the Codex config.toml keys owned by
# guidance/codex-main.toml and guidance/codex-context.toml.
# Unrelated settings are preserved; a timestamped backup is written on change.
# Flags: --check | --dry-run
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/agentpack.py" codex --only config "$@"

#!/usr/bin/env bash
# Compile pack -> Codex: agents (~/.codex/agents), skills (~/.agents/skills),
# ~/.codex/AGENTS.md, and the owned keys from guidance/codex-main.toml and
# guidance/codex-context.toml inside ~/.codex/config.toml (other settings kept).
# Flags: --check | --dry-run, --prune, --diff, --only agents,skills,agents-md,config
# Logic lives in lib/agentpack.py (shared by every exporter).
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/agentpack.py" codex "$@"

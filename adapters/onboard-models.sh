#!/usr/bin/env bash
# Interactive or non-interactive model onboarding for the agent definition pack.
# Discovers available models for a harness, prompts (or accepts --set / --answers)
# for main + each capability, and writes profiles/<name>.yaml (default: personal)
# without touching shipping profiles/codex.yaml or profiles/claude.yaml.
# See skills/onboard-models and SCHEMA.md "Model onboarding".
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/onboard_models.py" "$@"

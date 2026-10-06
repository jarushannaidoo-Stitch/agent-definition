#!/usr/bin/env bash
# Compile pack skills -> hermes skill folders (SKILL.md). Keeps
# "## Harness notes: hermes" sections. Output: $HERMES_SKILLS_OUT
# (default ~/agents/hermes-skills) plus .agentpack-resolved from profiles/hermes.yaml
# ($HERMES_PROFILE). Skills-only. See README and harnesses/hermes.yaml.
# Flags: --check | --dry-run, --prune, --diff, --profile NAME, --explain
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/agentpack.py" hermes "$@"

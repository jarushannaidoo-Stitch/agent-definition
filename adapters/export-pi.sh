#!/usr/bin/env bash
# Compile pack skills -> pi skill folders (SKILL.md). Keeps
# "## Harness notes: pi" sections. Output: $PI_SKILLS_OUT
# (default ~/agents/pi-skills) plus .agentpack-resolved from profiles/pi.yaml
# ($PI_PROFILE). Skills-only. See README and harnesses/pi.yaml.
# Flags: --check | --dry-run, --prune, --diff, --profile NAME, --explain
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/agentpack.py" pi "$@"

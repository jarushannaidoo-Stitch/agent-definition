#!/usr/bin/env bash
# Compile pack skills -> Grok Bot sand-workflow skill folders (SKILL.md with
# name + description frontmatter, companions copied verbatim). Keeps
# "## Harness notes: grokbot" sections and drops codex/cursor ones.
# Output: $GROKBOT_SKILLS_OUT (default ~/agents/grokbot-skills), plus a
# .agentpack-resolved sidecar from profiles/grokbot.yaml ($GROKBOT_PROFILE).
# Skills-only: no agents, AGENTS.md or config. This never writes to a Grok Bot
# box; copy or sync the out dir into the box workflows folder yourself
# (see README, "Grok Bot").
# Flags: --check | --dry-run, --prune, --diff, --profile NAME, --explain
# Logic lives in lib/agentpack.py (shared by every exporter).
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/agentpack.py" grokbot "$@"

#!/usr/bin/env bash
# Compile pack skills -> Claude Code skill folders (SKILL.md with name +
# description frontmatter, companions copied verbatim). Keeps
# "## Harness notes: claude" sections and drops other harness notes.
# Output: $CLAUDE_SKILLS_OUT (default ~/agents/claude-skills), plus a
# .agentpack-resolved sidecar from profiles/claude.yaml ($CLAUDE_PROFILE).
# Skills-only: no agents, AGENTS.md or config. This never writes into
# ~/.claude/skills by default; copy or sync the out dir there yourself
# (see README, "Claude Code").
# Flags: --check | --dry-run, --prune, --diff, --profile NAME, --explain
# Logic lives in lib/agentpack.py (shared by every exporter).
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/lib/agentpack.py" claude "$@"

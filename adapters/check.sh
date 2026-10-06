#!/usr/bin/env bash
# Verify every installed copy against the pack. Writes nothing.
# Exit 0 clean, 1 drift, 2 error. Extra flags (e.g. --diff) are passed through.
# Always checks codex + cursor. Other registered harnesses (grokbot, claude, pi,
# hermes, ...) are checked only when their skills out dir already exists
# (see harnesses/<name>.yaml out_default / $OUT_ENV). Run the matching
# ./adapters/export-<name>.sh once to opt in.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
status=0
# Prefer registry-driven list; fall back if the meta command fails.
mapfile -t harnesses < <(python3 "$here/lib/agentpack.py" list-harnesses --checkable 2>/dev/null | awk '{print $1}')
if [[ ${#harnesses[@]} -eq 0 ]]; then
  harnesses=(codex cursor)
  echo "== note: list-harnesses unavailable; checking ${harnesses[*]}"
fi
for harness in "${harnesses[@]}"; do
  echo "== $harness"
  python3 "$here/lib/agentpack.py" "$harness" --check "$@"
  rc=$?
  (( rc > status )) && status=$rc
done
exit $status

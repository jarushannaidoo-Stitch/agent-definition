# Queue when disconnected

Use this when a git/PR publish (sign, rewrite, push, draft PR) needs the user's registered computer and that machine is offline.

## Rule
If the harness reports the user's computer as disconnected, or a command targeted at that computer fails because it is unavailable, do not skip the job, do not ask the user to reconnect, and do not drop the CoS/user request. Queue it and retry until it lands.

## How
1. Keep the todo `in_progress`.
2. Re-check the machine's connection and retry the same machine-targeted `run_command` when you next wake, or after a short wait if you are already in the turn.
3. When the machine is connected, run the original sign/push unchanged (fetch origin/main, rewrite/sign with `git commit -S`, push; raise the harness's approval card if a push is blocked).
4. Only report a blocker if the job itself failed after the machine was online (signature, conflict, rejected push).

## Tools
- `run_command`: run the sign/push on the user's computer, and check whether it is connected.

## Harness notes: grokbot
- Connection status: ListMachines (disconnected vs connected).
- Machine-targeted command: Shell with machineId set to the user's laptop.
- Short in-turn wait: AwaitShell with no shell_id (sleeps for block_until_ms).
- Blocked push: retry the same Shell call with request_smart_mode_approval true and smart_mode_block_reason set to the exact Auto-review reason.

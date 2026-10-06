# Stitch publication requirements

Read before preparing commits, publishing, repairing or restacking Stitch work. The standing approval, Git-role and draft-PR boundaries in `AGENTS.md` still apply.

- Use `git commit -S` with Jarushan's existing GPG configuration on his machine. Do not request or embed a key ID. Cloud agents cannot sign; Git replays and signs their work in an isolated local worktree. If an authorized rewrite requires a force-push, use `--force-with-lease`.
- Keep commits small and focused for review and selective rollback. Preserve and replay every feature commit, including repairs, onto integration in dependency order. Never replace the series with one snapshot commit. Feature loop owns checkpointing, source-to-integration mapping and replay verification.
- Initial authors use permitted throwaway branches; cloud authors may use `cursor/` branches. Git alone publishes tests and implementation on the exact Linear branch with a conventional title and repository PR template. Do not invent publication branch prefixes.
- Verify required GitHub Actions on the exact published SHA, including after repair or restack. Report draft publication and green CI separately from ready, merged, landed or deployed. A green draft alone is not Done.
- On laptop disconnection, CoS retains the unsigned queue and dispatches Git when the laptop is available. Do not create a separate Git polling or retry routine, and do not change the approved branch/base while waiting.

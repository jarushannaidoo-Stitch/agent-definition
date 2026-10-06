# Unslop code

Companion to the **unslop** skill (prose). When Styla is requested, it uses these criteria for read-only review; invoking this skill for a rewrite requires separate authorization. Cuts AI-shaped code, not architecture.

Do not relitigate where SQL lives, who owns a transaction, or which package is the factory. Those follow the frozen spec, with Arc providing architecture advice to CoS. This skill is names, shape, and files.

## Always apply

1. **Readable names.** Call it what it is (`attempt_id`, `outbox_record`, `connection`). No one-letter or cryptic names (`k`, `r`, `rec`, `v`).
2. **Single responsibility.** Small classes. One reason to change per module. Split files by concern.
3. **OOP surface.** Public API is methods on small classes (`ChatService`, facades, factories, adapters). `Protocol` is the interface. Not a pile of module-level functions. No `classes/` folder.
4. **One concern per file.** SQL in a repository package. Row types in `entities.py`. Domain/handler models in `models.py`. Facade is thin methods only (no types, no SQL). Do not pile them into `facade.py`.
5. **File names are representative.** The file is named for the thing in it. Python module is snake_case of the class: `ChatService` lives in `chat_service.py`, not `execute.py`. Not `ChatService.py`.
6. **Enum members are `SCREAMING_SNAKE_CASE`.** `Provider.LITELLM`, not `== "litellm"`. Parse env strings into the enum. Unknown values fail closed.
7. **Neat over clever.** Easy to read. No god files. No nested helpers that hide the flow.
8. **Comments and leftover prose** still go through the **unslop** skill (no em dash soup, no puffery).

## Do not

- Invent extra types or layers "for cleanliness"
- Rename public contracts or catalog strings
- Open a GitHub PR
- Rewrite architecture fixed by the captain-approved spec

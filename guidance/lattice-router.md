# lattice-router repository rules

These rules apply only to lattice-router, not to Stitch's TypeScript services.

- Packages live in `src/data_plane`, `src/control_plane`, `src/worker` and `src/shared`. Use representative module names matching the snake_case class name.
- Use OOP and Protocol. Facades own transactions and nothing else; keep SQL and types outside the facade.
- Enum members use `SCREAMING_SNAKE_CASE`. Do not use `isinstance` ladders.
- Public request/response types belong to the relevant plane's domain. HTTP belongs in controllers only.
- Tests live in the plane's `__tests__/`. Do not add filler dependencies to quiet CI.
- Do not clone lattice-router onto the agent box. Cloud agents use the Cursor GitHub App.

## Summary

<!-- What changed and why? Keep it to a few sentences. -->

## Related issues

<!-- Use "Closes #123" to close the issue automatically when this PR merges. -->

## Testing

<!-- List the commands you ran and their results. Delete or explain unchecked rows. -->

- [ ] `pnpm lint`
- [ ] `pnpm typecheck`
- [ ] `pnpm test`
- [ ] `pnpm --filter web build`
- [ ] Django: `python manage.py check` and `pytest`
- [ ] Platform: `ruff check`, `ruff format --check`, `mypy`, and unit tests
- [ ] Not applicable (documentation or configuration only) — explain why:

## Checklist

- [ ] Changes are focused and match the existing structure and style
- [ ] Migrations are committed when Django models changed
- [ ] Generated artifacts were regenerated when the API schema changed
      (`openapi.json` and `packages/api-client-generated`)
- [ ] `AGENTS.md` or docs updated when commands, tooling, or the CI gate changed
- [ ] No secrets, tokens, credentials, or personal data are included

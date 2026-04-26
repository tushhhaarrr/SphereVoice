## What
<!-- Brief description of what this PR does -->

## Why
<!-- Why is this change needed? Link to issue if applicable -->

## How to test
<!-- Steps to verify this works -->

## Checklist

### Code Quality
- [ ] Lint passes (`ruff check .` / `pnpm lint`)
- [ ] Type check passes (`mypy` / `tsc --noEmit`)
- [ ] No `# type: ignore` or `Any` without justification
- [ ] No hardcoded secrets, API keys, or passwords

### Testing
- [ ] Tests added or updated for changed code
- [ ] All tests pass (`pytest` / CI green)

### Observability
- [ ] Errors are logged with context (not silently swallowed)

### Security
- [ ] No new secrets committed to code
- [ ] RLS policies respected (tenant isolation)

### Branch
- [ ] Branched from `dev`
- [ ] Squash-mergeable (clean commit history)

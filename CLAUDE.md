# Claude Code — project guidelines

## Git workflow (mandatory)

### Before starting any work
Always pull the latest changes from `main` before touching any file:
```bash
git checkout main
git pull
```
If there are local uncommitted changes, stash them first (`git stash`), pull, then reapply (`git stash pop`).

### Branch policy
**Work directly on `main`.** Do not create feature branches unless explicitly asked to by a collaborator. The previous `connect-engine-to-web-backend` branch was a one-off; that pattern should not be repeated.

### Pushing during a work session
Push to GitHub periodically — at minimum after every logical unit of work is complete (a new file, a bug fix, a working feature). Do not accumulate many changes locally before pushing. A good rule: if you have made changes that you would not want to lose, push them now.

```bash
git add <specific files>
git commit -m "concise description of what changed and why"
git push
```

### Pushing at the end of a session
Always push before finishing a session, even if the work is partial. A commit message like `"wip: partial implementation of X"` is acceptable — leaving unpushed work locally is not.

### Never
- Do not push directly to a branch other than `main` without explicit instruction.
- Do not force-push (`git push --force`).
- Do not commit `.env`, secrets, or large binary files.

## Code conventions
- Follow the existing style in each file — no reformatting of unrelated code.
- Run `pytest tests/ -q --override-ini="addopts="` before pushing to confirm nothing is broken.
- Do not add new dependencies without checking with the team first.

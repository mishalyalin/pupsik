# Contributing

PRs are welcome. This toolkit is meant to be forked, customized, and extended. Patches that improve the generic, public layer are appreciated.

## The one hard rule: no personal data, ever

**No personal data lands in this repo.** Not yours, not mine, not anyone's. This is non-negotiable.

If you fork this and customize it, keep your fork private or strip personal data before pushing back. Acceptable identifiers in PRs: generic placeholders like `Alice`, `Bob`, `Carol`, `Acme Corp`, `Vendor X`, `Project Foo`, `$HOME`, `/path/to/your/workspace`.

Before opening a PR: grep your diff for anything that looks personal - real names, real emails, real phone numbers, real company names, real addresses, real account numbers. Remove it.

The CI runs a privacy check on every push. It will fail your build if anything sensitive sneaks through. Save yourself the round-trip and run it locally first:

```bash
bash .github/scripts/privacy-check.sh --include-untracked
```

### Branch protection on the upstream main

As of 2026-05-19, `mishalyalin/pupsik:main` has branch protection enabled. The "Paranoid privacy scan" CI check MUST pass before any PR can merge. There's no override, even for the repo owner. If your PR fails the privacy check, the merge button stays grey - fix the flagged content and push again.

Run the scan locally before pushing:

```bash
bash .github/scripts/privacy-check.sh --include-untracked
```

If it passes locally but fails in CI, that usually means an untracked file landed in the diff via a later commit. Check `git status` before pushing.

## Filing issues

A good issue has:

1. What you expected to happen.
2. What actually happened.
3. The command you ran or the file you were editing.
4. Your OS, Node version (`node --version`), Python version (`python3 --version`), Claude Code CLI version (`claude --version`).
5. The smallest reproduction you can produce - ideally a single command or a tiny markdown file that triggers the bug.

## Pull requests

1. Fork. Topic branch off `main`.
2. Keep the change focused. One logical change per PR is easier to review and merge.
3. If you change behaviour, update the relevant doc (`README.md`, `HOW_IT_WORKS.md`, `UPGRADING.md`, `MODULAR.md`, or `CHANGELOG.md`).
4. New feedback rule? Drop the template in `memory_templates/` and add a one-line pointer in `templates/critical-rules.md.template`.
5. Privacy grep before opening (see above).
6. Short PR description: what changed, why, any caveats.

### How upstream sync handles your commits

My local publish flow refuses to push if `origin/main` is ahead of my clone. So once your PR merges, I pull (or rebase on) your work before pushing my next round. Your commits won't get accidentally rolled back by an automated re-publish.

## Code style

- **Python:** PEP 8. Tools target Python 3.10+. Type hints where they help, not as decoration.
- **Shell:** Bash, POSIX-compatible where reasonable. Idempotent. Safe to re-run.
- **Markdown:** Direct, no fluff, short paragraphs. Code blocks for anything you want the reader to copy.
- **TypeScript (MCP servers):** Match the file's existing style. Compile with `npm run build` before submitting.

## What this toolkit is and isn't

This is a **generic toolkit**. Every file you submit should make sense to a fresh user who has never met any of us. If something only makes sense to your specific workflow, it belongs in your fork - not here.

Forking, customizing, and using it for your own workflow is the expected mode. Keep this upstream repo focused on the generic layer.

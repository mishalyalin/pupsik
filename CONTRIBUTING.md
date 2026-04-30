# Contributing

Thanks for considering a contribution. This toolkit is meant to be forked,
customized, and extended. Patches that improve the generic, public layer are
welcome.

## Privacy guarantee

**No personal data ever lands in this repository.** That is a hard rule, not a
guideline.

If you fork this and customize it for your own use, keep your fork private or
strip personal data before pushing back here. Acceptable identifiers in PRs:
generic placeholders like `Alice`, `Bob`, `Carol`, `Acme Corp`, `Vendor X`,
`Project Foo`, `$HOME`, `/path/to/your/workspace`.

When opening a PR, please run a grep for anything that looks personal —
real names, real email addresses, real phone numbers, real company names,
real account numbers, real addresses — and remove it before submitting.

## Filing issues

A good issue includes:

1. What you expected to happen.
2. What actually happened.
3. The exact command you ran or the file you were editing.
4. Your OS, Node version (`node --version`), Python version (`python3 --version`),
   and Claude Code CLI version (`claude --version`).
5. The smallest reproduction you can produce — ideally, a single command or a
   minimal markdown file that triggers the behaviour.

## Pull requests

1. Fork the repo and create a topic branch off `main`.
2. Keep changes focused. One logical change per PR is easier to review.
3. If you change behaviour, update the appropriate document
   (`README.md`, `HOW_IT_WORKS.md`, `UPGRADING.md`, `MODULAR.md`, or `CHANGELOG.md`).
4. If you add a new feedback rule template, drop the file in `memory_templates/`
   and add a one-line pointer in `templates/critical-rules.md.template`.
5. Run the privacy grep before opening the PR (see above).
6. Open the PR with a short description: what changed, why, and any caveats.

### Maintainer note: how upstream sync handles contributor commits

The maintainer's local publish flow refuses to push if `origin/main` has
commits ahead of the local clone. That means once your PR merges into
`main`, the maintainer pulls (or rebases on) your work before pushing
their next round of changes — your commits aren't accidentally rolled
back by an automated re-publish.

## Code style

- **Python:** PEP 8. The existing tools target Python 3.10+. Use type hints
  where they clarify intent; don't over-engineer.
- **Shell:** No strong opinion. Bash, POSIX-compatible where reasonable. Keep
  scripts idempotent and safe to re-run.
- **Markdown:** Use the same tone as the rest of the docs — direct, no fluff,
  short paragraphs, code blocks for anything the reader will copy.
- **TypeScript (MCP servers):** Match the style of the file you're editing.
  Compile with `npm run build` before submitting.

## What this toolkit is and is not

This is a **generic toolkit**. Every file you submit should make sense to a
fresh user who has never met any of the original contributors. If a piece of
text only makes sense to you and your team, it belongs in your fork — not in
this repo.

If you fork it, change it, and use it for your own workflow: that's the
expected mode. The toolkit is designed to be customized. Please keep this
upstream repo focused on the generic layer.

# Third-Party Attributions

Patterns, code, and conventions in this toolkit that were adapted from external open-source projects. Maintained per the "do attribution properly" discipline: every imported pattern lists source URL, author, license, adaptation type, and what was changed vs taken verbatim.

License compatibility note: this toolkit is MIT-licensed (see `LICENSE`). Imports listed below are all compatible with MIT.

## gbrain (Garry Tan)

- **Source:** https://github.com/garrytan/gbrain
- **Author:** Garry Tan
- **License:** MIT (verified via `gh api repos/garrytan/gbrain --jq '.license.spdx_id'`)
- **What it is:** "Personal knowledge brain and GStack mod for agent platforms" - TypeScript/Bun harness + markdown skills + PGLite/Postgres pgvector.
- **Why we drew from it:** the "thin harness, fat skills" architecture and several specific patterns (friction protocol, doctor, output rules, two-layer pages) that translate cleanly into this Python/SQLite/ChromaDB stack.

| Imported pattern | Source file in gbrain | Date | Adaptation type | Our location |
|------------------|----------------------|------|-----------------|--------------|
| Friction Protocol (severity taxonomy + CLI shape) | `skills/_friction-protocol.md` | 2026-05-07 | adapted | `tools/note.py` (`friction` subcommand) |
| Doctor (health-check + safe-auto-fix) | `gbrain doctor` / `gbrain orphans` / `gbrain repair-jsonb` (described in `llms.txt`) | 2026-05-07 | adapted | `tools/doctor.py` |
| Output Rules (cross-cutting quality standards) | `skills/_output-rules.md` | 2026-05-07 | adapted | per-rule files in `memory_templates/feedback_*.md` (Deterministic Links, No Slop, Exact Phrasing Preservation, Title Quality) |

### Adaptation notes

**Friction Protocol** - taken verbatim: severity taxonomy (`blocker` / `error` / `confused` / `nit`) and CLI command shape (`--severity`, `--phase`, `--message`, `--hint`). Adapted: backing store via `note.py` + ChromaDB instead of a separate gbrain CLI; storage path `memory/friction/<date>-<severity>-<slug>.md` with upsert-by-`(phase, severity)` incrementing a `counter` field for repeat-pattern detection. Our additions: counter-based escalation (counter >= 3 surfaces in morning briefing), integration with the existing memory-files ChromaDB collection.

**Doctor** - taken: the `check` / `fix-safe` / `orphans` command-suite shape and the "deterministic checks with safe auto-fix" architecture. Adapted: 13 specific checks tuned to this stack (file-system + ChromaDB + SQLite contacts.db, no Postgres / no JSONB). Constraint: SAFE auto-fixes only - no LLM-driven content rewrites - so the tool can run unattended in cron without risk of misinterpreting and clobbering user content.

**Output Rules** - taken verbatim with attribution: 4 rules (Deterministic Links, No Slop, Exact Phrasing Preservation, Title Quality). Adapted: examples reframed for this toolkit's voice. Our additions: cross-references to the 7 pre-existing per-rule feedback files in `memory_templates/` (short dashes, no Office, save outputs, verify before showing, weekday-from-iso, kids' names exactness, never-extract-signatures); together the 11 form a single cross-cutting checklist.

## How attribution lives in the codebase

For every import, attribution is layered in 5 places (overkill is intentional - any single layer can drift, but five together do not):

1. **Frontmatter** (markdown) or **header docstring** (Python) on the imported file: `adapted-from`, `source-url`, `source-license`, `adaptation-type`.
2. **Body cross-references** in the imported file pointing at adjacent files and the source.
3. **This file** (central tracker) with the row in the table above.
4. **One-line pointer** in the project's main rules file (loaded each session).
5. **Index entry** in the memory index file.

If you fork this toolkit and replace these imports with your own implementations, scrub these layers in lockstep so attribution stays accurate.

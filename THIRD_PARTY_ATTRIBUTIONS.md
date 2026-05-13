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

## obra/superpowers (Jesse Vincent)

- **Source:** https://github.com/obra/superpowers
- **Related repo:** https://github.com/obra/private-journal-mcp (schema source for the knowledge sub-collections below)
- **Author:** Jesse Vincent
- **License:** MIT (verified via the upstream repo's `LICENSE` file)
- **What it is:** A library of Claude Code skills plus a private-journal MCP that categorises atomic notes into project/world/user buckets.
- **Why we drew from it:** Two debugging-discipline rules (systematic phase walk + plan specificity) and the world/user knowledge category split fit cleanly on top of this toolkit's existing `note.py` + ChromaDB stack.

| Imported pattern | Source file in obra/superpowers | Date | Adaptation type | Our location |
|------------------|---------------------------------|------|-----------------|--------------|
| Systematic Debugging (4-phase rubric + hard gates) | `skills/systematic-debugging` | 2026-05-13 | adapted | `memory_templates/feedback_systematic_debugging.md` |
| Junior-Engineer Plan Test (writing-plans specificity rubric) | `skills/writing-plans` | 2026-05-13 | adapted | `memory_templates/feedback_junior_engineer_plan_test.md` |
| World / User knowledge categories (schema only, not the MCP server) | `obra/private-journal-mcp` (related repo) | 2026-05-13 | schema-only cherry-pick | `tools/note.py` (subcommands), `tools/memory_search.py` (knowledge subtype), `memory_templates/world_knowledge/_PROTOCOL.md`, `memory_templates/user_context/_PROTOCOL.md` |

### Adaptation notes

**Systematic Debugging** - taken verbatim: the 4-phase rubric (Reproduce / Isolate / Diagnose / Fix) and the hard-gate framing ("no fix before isolation", "no phase 3 skip", "stop at 30 minutes without isolation"). Adapted: phrased as a user-voice feedback rule in this toolkit's style; cross-referenced against the 2-agent rule and the capture-knowledge rule (a phase-3 root-cause claim is exactly what `note.py learning` is for).

**Junior-Engineer Plan Test** - taken verbatim: the "an enthusiastic junior engineer could execute it cold, without coming back with questions" framing and the pass/fail criteria shape (absolute paths, exact commands, explicit success criteria, named assumptions). Adapted: phrased as a user-voice feedback rule; generic bad/good examples replace the original's specific examples; cross-referenced against the 2-agent rule (a Checker can only verify if the brief was specific enough) and against the systematic-debugging rule (a Phase 2 isolation statement is itself a junior-engineer-plan-test for bugfix work).

**World / User knowledge categories** - taken verbatim: the category concept (world_knowledge = facts about the world, user_context = facts about the user). NOT taken: the MCP-server implementation (this toolkit uses `note.py` + the existing ChromaDB knowledge collection). Adapted: storage as per-file markdown in `memory/world_knowledge/` and `memory/user_context/`; upsert-by-slug semantics matching the learning/decision/research types; surfaces via `memory_search.py search` with `subtype: world_knowledge` / `subtype: user_context`. Our additions: explicit separation from `feedback_*.md` files (those are prescriptive rules Claude MUST follow; user_context is descriptive observations for planning).

## How attribution lives in the codebase

For every import, attribution is layered in 5 places (overkill is intentional - any single layer can drift, but five together do not):

1. **Frontmatter** (markdown) or **header docstring** (Python) on the imported file: `adapted-from`, `source-url`, `source-license`, `adaptation-type`.
2. **Body cross-references** in the imported file pointing at adjacent files and the source.
3. **This file** (central tracker) with the row in the table above.
4. **One-line pointer** in the project's main rules file (loaded each session).
5. **Index entry** in the memory index file.

If you fork this toolkit and replace these imports with your own implementations, scrub these layers in lockstep so attribution stays accurate.

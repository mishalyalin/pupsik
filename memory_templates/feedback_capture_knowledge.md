---
name: Capture knowledge in-flight via note.py
description: 🔴 MANDATORY — the MOMENT an insight / decision / research finding emerges (even mid-investigation), capture it via `note.py`. Don't wait for the topic to close. If understanding evolves, re-run with the SAME title — upsert overwrites the existing note.
type: feedback
---
# 🔴 MANDATORY: Capture knowledge in-flight (moment-of-emergence)

## The rule

The **moment** a meaningful insight, decision, or research finding emerges in a session, capture it via `note.py` **immediately**. Don't wait until "the topic closes" — the capture happens at the moment of crystallisation, even mid-investigation.

If understanding later changes, re-run `note.py` with the **same title**. The slug matches the existing file and `note.py` **upserts** it (merges tags, refreshes the `updated:` frontmatter, rewrites the body). **One note per topic, kept current** — not a chain of revisions.

## Why

Without auto-capture, knowledge dies in chat context. Five days later you ask "what was that vendor's freight quote?" — and the answer that was once in conversation is **gone**. Compaction ate it. A new session can't see it. ChromaDB doesn't index it.

Moment-of-emergence capture is the only way to preserve atomic knowledge so that:
- It surfaces via `memory_search.py search "<keywords>"` weeks later.
- It lives as a standalone MD file with frontmatter — readable, grep-friendly, version-controllable.
- It enters a ChromaDB collection automatically (`learnings` / `decisions` / `research`).
- When understanding evolves, the **same file** updates — not a duplicate.

## When to capture (threshold)

**Capture if:** "Would this matter if I (or future-me / a teammate) asked about it 3 weeks from now?" → YES → capture **at the moment it emerges**, not at the end of the topic.

Concretely:
- ✅ **Learning / insight** — something you learned about a vendor, market, regulator, tool, pattern, or anti-pattern.
- ✅ **Decision** — a choice was made between alternatives (even small ones: "use Vendor A, not Vendor B"; "ship 150×150×150 box, not 120×120×120").
- ✅ **Research finding** — a web / registry / competitor / regulator search produced a concrete fact + source (URL, date, document).

**Don't capture:**
- ❌ Trivial lookup ("what's their email?")
- ❌ Restatement of a known fact already in `CLAUDE.md`.
- ❌ Side-comments, banalities, meta-remarks about the work itself.
- ❌ "I did X" as a progress report — that belongs in journal, not learnings.

## Where it goes

`note.py` writes the file into the right subdir automatically:
- `learning` → `~/Desktop/claude/memory/learnings/YYYY-MM-DD-<slug>.md`
- `decision` → `~/Desktop/claude/memory/decisions/YYYY-MM-DD-<slug>.md`
- `research` → `~/Desktop/claude/research/YYYY-MM-DD-<slug>.md`

**Filename keeps the FIRST-emergence date** (when it was first written). Upsert does not change the filename. Frontmatter: `created:` (date when first written, never changes) + `updated:` (today, changes on each upsert).

## Upsert behaviour (default)

If a file with the same slug already exists in the target subdir (regardless of date prefix), `note.py`:

- **Opens** the existing file.
- **Preserves** `created:` (or migrates `date:` → `created:`).
- **Sets** `updated: <today>`.
- **Merges tags** (union, dedup case-insensitive, existing first).
- **Overwrites the body** cleanly. The previous version is not retained — the rule is "current version is the source of truth, history lives in git, not in frontmatter bloat". Use `--append` if you want to preserve prior context.
- **Prints** `updated: <path>` (not `wrote:`) so you can see the upsert happened.

Tag-merge decision: **union** (not replace). Re-running with a subset of tags keeps the existing ones. To shrink the tag list, edit the file by hand.

Versions-log decision: **clean overwrite, no history**. Current version = source of truth. History lives in git, not in the note frontmatter.

## Edge cases

**Genuinely unrelated topic with the same slug** (slug collision from similar titles):
```bash
note.py learning "Different topic, same slug" "..." --new
# print: wrote: <path>  (NEW file, not an upsert)
```
`--new` forces a new file (uses the existing `unique_path` helper with `-2`/`-3` suffix).

**Evolving research where you want to keep history** (e.g. vendor prices over time):
```bash
note.py research "Vendor X pricing" "Q1 €0.49/pc" --tags "vendor-x"
# Later:
note.py research "Vendor X pricing" "Q2 €0.51/pc — bumped 4%" --append
# Body becomes: "## Update YYYY-MM-DD\n\nQ2 €0.51/pc...\n\n[previous body]"
```

**If you realise the title was wrong** — rename the file by hand and re-run `note.py` with the right title. The old file is not auto-deleted.

## How to apply

When an insight surfaces during work, run **immediately**:

```bash
# Learning — after a meaningful insight about your project / vendor / customer
python3 ~/Desktop/claude/tools/note.py learning "Vendor X minimum order is 5k pcs" \
  "Confirmed MOQ on outerbox = 5,000 pcs. Below that, tooling cost €450 still applies but per-unit jumps to €4.10. Implication: if launch volume <5k, switch to a generic-box supplier." \
  --tags "vendor-x,packaging,moq" --project "Packaging Design"

# Decision — when you (or your team) chose between alternatives
python3 ~/Desktop/claude/tools/note.py decision "Use Vendor A as baseline 3PL" \
  "After RFQ across A/B/C/D/E, Vendor A wins on speed-to-onboard and per-shipment freight cost." \
  --alternatives "VendorA,VendorB,VendorC,VendorD,VendorE" --rationale "VendorA = €0 setup, EU lane €400-500, default carrier integration. VendorB silent. VendorC premium pricing." \
  --project "Logistics"

# Research — when a search produced a concrete fact + source
python3 ~/Desktop/claude/tools/note.py research "NL food regulator registration timeline" \
  "Regulator accepted entity registration in <72h. Client number issued. No fee. Required for any food operation under the entity." \
  --sources "https://example.regulator.gov/registers" --query "food regulator entity registration timeline"

# A week later, a vendor sent a correction — re-run with the SAME title:
python3 ~/Desktop/claude/tools/note.py learning "Vendor X minimum order is 5k pcs" \
  "REVISED: MOQ re-confirmed = 3,500 pcs, not 5,000. Tooling cost €450 unchanged. Per-unit at MOQ floor = €3.85." \
  --tags "vendor-x,packaging,moq,revised"
# print: updated: <path>  ← same file, refreshed
```

Body tone: **2-5 sentences max, atomic — not an essay**. Title = noun-phrase (not a question). Tags = lowercase, comma-separated.

## Anti-pattern (what NOT to do)

- ❌ "I'll capture it later / when the topic closes" — no. **Now** is the only reliable moment.
- ❌ Only in journal / briefing / outputs — those are not findable as atomic knowledge.
- ❌ Long essay in body — atomic, not prose.
- ❌ Duplicate of `CLAUDE.md` / project memory — `note.py` is for **new** atoms, not copies.
- ❌ Creating a new title for each revision ("Vendor X quote v2", "Vendor X quote final") — upsert with the same title.

## Pattern (how it SHOULD work)

```
Insight crystallises mid-conversation
  ├─ STOP (don't "I'll do it later")
  ├─ Run note.py with the appropriate type + same title each time
  ├─ Confirm "wrote: <path>" (new) or "updated: <path>" (upsert)
  └─ Resume work

Later: understanding evolves
  ├─ note.py with the same title + new body
  ├─ Confirm "updated: <path>"
  └─ Done — single canonical note, current state
```

Time-to-capture ≈ 30 seconds. Cost of skipping = knowledge lost forever.

## Full reference

- CLI: `~/Desktop/claude/tools/note.py --help`
- Search: `python3 ~/Desktop/claude/tools/memory_search.py search "query"`
- One-liner rule: `~/.claude/rules/critical-rules.md`
- This file: `memory/feedback_capture_knowledge.md` (full context)

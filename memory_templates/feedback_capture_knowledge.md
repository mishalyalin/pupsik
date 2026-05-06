---
name: Capture knowledge in-flight via note.py
description: 🔴 MANDATORY — the MOMENT an insight / decision / research finding emerges (even mid-investigation), capture it via `note.py`. Don't wait for the topic to close. Never ask the user "should I capture this?" — just capture. If understanding evolves, re-run with the SAME title; upsert overwrites the existing note.
type: feedback
---
# 🔴 MANDATORY: Capture knowledge in-flight (moment-of-emergence)

## Trigger

The **moment** a meaningful insight, decision, or research finding crystallises in a session, capture it via `note.py` **immediately**. Don't wait until "the topic closes" — the capture happens at the moment of emergence, even mid-investigation.

If understanding later changes, re-run `note.py` with the **same title**. The slug matches the existing file and `note.py` **upserts** it (merges tags, refreshes the `updated:` frontmatter, rewrites the body). **One note per topic, kept current** — not a chain of revisions.

## 🔴 Never ask permission (no-ask rule)

**NEVER ask the user "should I capture this?", "want me to save this?", or any variant.** Default = **capture**. The user will delete (`rm` the file, or tell you to) only if a particular capture was a mistake. Asking-by-default = guaranteed lost knowledge: by the time the user answers, context has moved on, the insight has decayed, and most of the time the answer is "yes, just do it" anyway.

The cost asymmetry favors over-capture: a bad note is one `rm` away; an uncaptured insight is gone forever.

The **threshold question** ("would this matter 3 weeks from now?") is the **model's silent decision**, NOT a question for the user. If you are *thinking* about whether to capture → that thinking IS the trigger → run `note.py` immediately. If unsure, capture; the upsert mechanism makes "wrong title" trivial to fix later.

**If you're thinking about whether to capture, you've already crossed the threshold. Capture.**

### Banned phrases

Do not emit any of these (or paraphrases). Capture first, then mention what landed in passing.

English:
- ❌ "Should I capture this?"
- ❌ "Want me to save this for later?"
- ❌ "Want this in memory?"
- ❌ "Should I note this down?"
- ❌ "Make a memory note now?"
- ❌ "Want a learning note from this?"

Russian (universal — keep as-is even if the user works in English):
- ❌ "Сделать сейчас memory note?"
- ❌ "Сохранить?"
- ❌ "Записать?"
- ❌ "Запомнить это?"
- ❌ "Хочешь запись?"
- ❌ "Делать ли memory note?"

**Correct pattern:** capture FIRST, then mention it in passing — "Captured as learning `<slug>` for future search" — so the user sees what landed without being asked to authorize it. Override cost: 5 seconds (delete the file). Asking cost: lost knowledge.

## Upsert by title (one note per topic)

Re-running `note.py` with the **same title** overwrites the existing file in place:

- **Preserves** `created:` (date when first written, never changes).
- **Sets** `updated: <today>`.
- **Merges tags** (union, dedup case-insensitive, existing first).
- **Rewrites the body** cleanly. The previous version is not retained — current version is the source of truth, history lives in git.
- **Prints** `updated: <path>` (not `wrote:`) so you see the upsert happened.

To force a new file when slugs collide on genuinely unrelated topics: pass `--new`. To preserve prior body and append a dated update section: pass `--append`.

## Use `--body-stdin` or `--body-file` for tricky text

Single-line shell-quoted bodies break on apostrophes, embedded quotes, or multi-line content. Two flags solve it:

```bash
# Heredoc — handles apostrophes, "quotes", and multi-line cleanly
python3 ~/Desktop/claude/tools/note.py learning "Title" --body-stdin <<'EOF'
Body with 'apostrophes', "quotes", and multi-line
all work — no escape gymnastics.
EOF

# File — when the body is already on disk (e.g. from a prior tool output)
python3 ~/Desktop/claude/tools/note.py learning "Title" --body-file /tmp/body.md
```

Reach for these whenever the body contains anything beyond plain ASCII letters and spaces. Default to `--body-stdin` when in doubt — it costs you one heredoc, saves you a quoting-hell debug loop.

## Threshold heuristics

**Capture if:** "Would this matter to me (or future-me, or a teammate) 3 weeks from now?" → YES → capture **at the moment it emerges**, not at the end of the topic.

Concretely:
- ✅ **Learning / insight** — something you learned about a vendor, market, regulator, tool, codebase pattern, or anti-pattern.
- ✅ **Decision** — a choice was made between alternatives (even small ones: "use Vendor A, not Vendor B"; "ship 150×150×150 box, not 120×120×120").
- ✅ **Research finding** — a web / registry / competitor / regulator search produced a concrete fact + source (URL, date, document).
- ✅ **Vendor commitment** — a price, lead time, MOQ, or SLA confirmed by the supplier.
- ✅ **Deadline shift** — a regulatory or contractual date moved.

**Don't capture:**
- ❌ Trivial lookup ("what's their email?").
- ❌ Restatement of a known fact already in `CLAUDE.md` or another memory file.
- ❌ Side-comments, banalities, meta-remarks about the work itself.
- ❌ Progress reports ("I did X today") — those belong in journal, not learnings.

## Where it goes

`note.py` writes the file into the right subdir automatically:
- `learning` → `~/Desktop/claude/memory/learnings/YYYY-MM-DD-<slug>.md`
- `decision` → `~/Desktop/claude/memory/decisions/YYYY-MM-DD-<slug>.md`
- `research` → `~/Desktop/claude/research/YYYY-MM-DD-<slug>.md`

**Filename keeps the FIRST-emergence date** (when first written). Upsert does not change the filename. Frontmatter: `created:` (first write, immutable) + `updated:` (today, changes on each upsert).

## Examples (generic)

```bash
# Learning — after a meaningful insight about a vendor / market / pattern
python3 ~/Desktop/claude/tools/note.py learning "Vendor X minimum order is 5k pcs" \
  "Confirmed MOQ on outerbox = 5,000 pcs. Below that, tooling cost still applies but per-unit jumps significantly. Implication: if launch volume <5k, switch to a generic-box supplier." \
  --tags "vendor-x,packaging,moq"

# Decision — when you (or your team) chose between alternatives
python3 ~/Desktop/claude/tools/note.py decision "Use Vendor A as baseline 3PL" \
  --alternatives "VendorA,VendorB,VendorC" \
  --rationale "Vendor A wins on speed-to-onboard and per-shipment freight cost; B silent; C premium." \
  --body-stdin <<'EOF'
After RFQ across A/B/C, Vendor A wins on speed-to-onboard and per-shipment freight.
Default carrier integration; no setup fee; baseline lane within target cost band.
EOF

# Research — when a search produced a concrete fact + source
python3 ~/Desktop/claude/tools/note.py research "NL food regulator registration timeline" \
  "Regulator accepted entity registration in <72h. Client number issued. No fee. Required for any food operation under the entity." \
  --sources "https://example.regulator.gov/registers"

# A week later, a vendor sent a correction — re-run with the SAME title:
python3 ~/Desktop/claude/tools/note.py learning "Vendor X minimum order is 5k pcs" \
  "REVISED: MOQ re-confirmed = 3,500 pcs, not 5,000. Tooling cost unchanged. Per-unit at MOQ floor adjusted." \
  --tags "vendor-x,packaging,moq,revised"
# print: updated: <path>  ← same file, refreshed
```

Body tone: **2-5 sentences, atomic — not an essay**. Title = noun-phrase (not a question). Tags = lowercase, comma-separated.

## Anti-pattern

- ❌ "I'll capture it later / when the topic closes" — no. **Now** is the only reliable moment.
- ❌ Asking "should I save this?" before capturing — banned (see "Never ask permission").
- ❌ Only in journal / briefing / outputs — those are not findable as atomic knowledge.
- ❌ Long essay in body — atomic, not prose.
- ❌ Duplicate of `CLAUDE.md` / project memory — `note.py` is for **new** atoms, not copies.
- ❌ Creating a new title for each revision ("Vendor X quote v2", "Vendor X quote final") — upsert with the same title.

## Pattern (how it should work)

```
Insight crystallises mid-conversation
  ├─ Pause (don't "I'll do it later", don't "should I save this?")
  ├─ Run note.py with the appropriate type + descriptive title
  ├─ Confirm "wrote: <path>" (new) or "updated: <path>" (upsert)
  └─ Resume work, mention capture in passing if relevant

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

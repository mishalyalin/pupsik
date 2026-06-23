# feedback_code_for_deterministic_tasks.md

Match the method to the nature of the task: if a task has one correct answer a function could compute the same way every time, WRITE CODE for it. If it genuinely needs judgment, REASON it - do not fake judgment with brittle code that only looks authoritative. Either way, the output is ALWAYS independently verified.

## The rule

1. **Deterministic task -> write code.** If you can write code that solves it and produces the same correct answer every run, write the code. Do NOT re-derive it by hand, by eye, or "in your head" each time - that is slower, drifts between runs, and is exactly where invented numbers/dates/sums walk in. Code written once is reproducible forever.

2. **Non-deterministic task -> don't fake it with code.** If the task genuinely needs judgment - natural language, tone, brand voice, intent classification, "are these two records the same entity?", reading fuzzy context - do NOT write brittle code that pretends to be deterministic (keyword lists, regex "classifiers", hard-coded heuristics that will be wrong on the next input). Use real reasoning. A fake-deterministic script is worse than honest judgment because it *looks* authoritative while being silently wrong.

3. **Always verify - both branches.** Code is never trusted because it "should work": run it against known input/expected output and have an independent checker read it. Judgment output is never shipped on one pass: an independent checker re-derives the conclusion from the sources. Verification is not optional in either case. "The script ran without error" is NOT the same as "the answer is correct."

## How to apply

**Ask first: does this task have one correct answer that a function could compute every time?**

- **Yes (deterministic) -> CODE IT.** Examples: date/time math, currency conversion at a fixed rate, weekday-from-ISO-date, parsing a known file/JSON/CSV format, field extraction from structured data, dedup, sort, count, set math, financial arithmetic (sums, totals, costs, margins), hashing/encryption, file moves, diffing, validating against a schema, regex over a known fixed format. Write the script, run it, check the output. If it will recur, prefer a saved tool over an ad-hoc one-liner - and grep for an existing implementation first (`feedback_pr_reuse_audit.md`).

- **No (judgment / language / fuzzy) -> REASON, don't code-fake.** Examples: writing prose in a specific voice, deciding whether an inbound message is actionable, marketing/brand copy, negotiation phrasing, summarizing, "is this the same person/company?", reading sentiment, prioritizing a list by importance. Use real reasoning (and any relevant skills/review panels). If you catch yourself building a keyword list or a regex to *approximate* a judgment call, stop - that is the anti-pattern.

- **Mixed -> split it.** Most real tasks are part deterministic, part judgment. Do the deterministic spine in code (pull the rows, compute the totals, extract the fields) and the judgment on top in reasoning (interpret, phrase, decide). Don't smear judgment into the code, and don't smear arithmetic into the prose.

**Then verify, always:**
- Code -> run it against a known case; for anything load-bearing, have an independent checker agent read the code AND confirm the output matches an expected value (`feedback_always_two_agents.md`).
- Judgment -> an independent checker re-derives the conclusion from the sources.
- Never present either as done on a single unverified pass.

## Anti-patterns

- "I'll just eyeball the sum / count these by hand / work out the weekday from the date" for something a one-liner computes exactly -> CODE IT. (Computing a weekday by pattern-matching instead of a date function is the canonical case - see `feedback_compute_weekday_dont_guess.md`.)
- "I'll write a quick classifier" (keyword/regex) for message intent, record-matching, tone, or any judgment call -> DON'T; reason it.
- "The script ran without error, so the answer is right" -> not verified. No-error != correct. Check the actual output against an expected value.
- "It's obviously correct, no need to test" -> that sentence is the precondition for the bug.

## Cross-references

- `feedback_always_two_agents.md` - the verification arm of this rule: a worker produces (code or judgment), an independent checker confirms before ship.
- `feedback_never_imagine_always_verify.md` - the primary rule; "deterministic -> code" removes a whole class of imagined numbers by computing them instead of recalling them.
- `feedback_compute_weekday_dont_guess.md` - the archetypal deterministic-must-be-code case.
- `feedback_pr_reuse_audit.md` - before writing new deterministic code, check for an existing implementation first.

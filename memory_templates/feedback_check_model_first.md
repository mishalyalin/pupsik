# Feedback: Check the model FIRST + cite source for EVERY number in outbound

A HARD GATE for numerical claims. Updated to blanket-mandatory after a second same-day violation where a draft outbound cited a launch-volume figure pulled from imagination when the actual model said an order-of-magnitude-higher number.

## What the user said

Set after a GTM session that recommended external-agency spend and ad-spend numbers without first checking the annual marketing budget: "Numbers without model = wrong numbers."

Upgraded after a draft outbound asked for a fee waiver built on an imagined launch-volume figure when the model said something much higher. Verbatim (translated; original was in Russian):

> You wrote me a very plaintive email about "X orders", but somehow you again didn't look at the model. The model says something completely different. And I'm tired of reminding you to fact-check FIRST. Before outputting any numbers, fact-check. Where is the fact-check? Not in your imagination, but in the places where it actually lives. Got it?

## The hard gate (blanket)

ANY outbound message containing numerical claims about your business -> MANDATORY pre-send checklist:

1. **Read the latest model output**. Currently the canonical file lives somewhere like `~/Desktop/claude/outputs/YYYY-MM-DD-<integrity-verdict>.md` (or whichever dated equivalent supersedes it). It contains your scenario matrix (e.g. Pess / Base / Opt) with Y1/Y3/Y5 revenue + EBITDA + cash positions.

2. **For monthly granularity**: yearly aggregates do NOT tell you launch-month volume. A ramped trajectory means the launch month is NOT (Y1 / 12). To get monthly:
   - Ask the user to paste the row from their Sheets, OR
   - Find and read the actual Sheets / Drive CSV / cashflow tab, OR
   - State explicitly: "I only have the Y1 aggregate; if you can paste the month-1 row, I can use it directly"

3. **Cite source for EVERY number** in the outbound:
   - GOOD: "Base scenario Y1 figure per integrity-verdict YYYY-MM-DD"
   - GOOD: "Month-1 launch volume N per model row the user pasted YYYY-MM-DD"
   - BAD: "we project ~Y" (no source)
   - BAD: "we launch with N units" (where did N come from? imagination)

4. **If a number is NOT in the model**, state the assumption explicitly AND ask the user to verify BEFORE sending. Never silently estimate.

## Scope: when this applies

ALL of the following:
- Email / DM / draft / chat outbound to a third party
- Briefings prepared for the user that they will forward to advisors / investors / partners
- Investor updates
- Negotiation asks (waivers, discounts, terms, pricing)
- Anywhere you cite volume, revenue, CAC, margin, burn, runway, orders, cash position, dates, or any other quantitative claim about the business

NOT internal-only:
- CLAUDE.md updates
- Memory captures (decisions / learnings / feedback)
- Code you write for tools

If in doubt, cite source anyway. It costs nothing.

## Locations to check (in priority order)

1. The latest dated integrity-verdict / model-output file in your `outputs/` directory
2. The bug / refactor audit files for the same model (methodology and detailed structure)
3. The underlying spreadsheet (actual monthly granularity; need to find URL or ask the user to paste)
4. The pricing-strategy doc (pricing assumptions)
5. International / regional rebuild docs if relevant
6. The user's pasted data in the current conversation (canonical when freshly pasted)

Adjust paths to wherever you save artefacts.

## The two representative violations

**GTM session (rule v1):** Recommended hiring an external agency + ad spend without reading the Y1 marketing budget. Y1 budget was a small share of a single recommendation's monthly burn; the proposed plan would have consumed it in 2-3 months. Rule v1 created.

**Waiver email (rule v2 upgrade):** Drafted a fee-waiver request to a logistics partner built on the assumption "we launch with X orders in month one". The model actually said roughly 10x that, at a comparable revenue figure. At the real volume the partner's per-order rate cleared their monthly floor comfortably - waiver ask was MOOT. Worse: it signalled to the partner's BD contact that the founder doesn't know their own volume, damaging negotiating position. Rule upgraded to HARD GATE.

Pattern: knew the rule existed, didn't check before composing, wrote a plausible-sounding wrong number. Plausibility-based number generation = fabrication. Banned.

## Anti-patterns

- BAD: "Conservative estimate, ~N" (where did N come from?)
- BAD: "We project ~$X Y1" (Pessimistic? Base? Optimistic?)
- BAD: "Launch volume to be determined" -> then putting a number in next paragraph anyway
- BAD: "I'll round it" (rounding the wrong number gives the wrong answer)
- BAD: Citing skill-methodology / industry-benchmark numbers when the model has actual numbers

## Right pattern

1. STOP before composing
2. Read latest model output
3. List every number that will appear in the outbound
4. For each number: cite source (file:line / user paste / spec sheet)
5. If source missing: ask the user or state explicitly as assumption
6. Compose
7. Re-audit numbers in the finished draft against sources
8. THEN save / send

## Related rules

- `feedback_never_imagine_always_verify.md` - the parent verify-everything rule
- `feedback_verify_project_state.md` - verify state before answering
- `feedback_never_ignore_own_rules.md` - rules mandatory not suggestions
- `feedback_verify_dont_imagine_external_brand.md` - direct evidence for external-brand claims

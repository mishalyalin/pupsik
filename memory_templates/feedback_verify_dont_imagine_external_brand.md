---
name: Verify-Dont-Imagine for external brand documentation
description: When documenting external brand patterns (competitor pricing, copy, funnel) for use in your own customer-comms work, state ONLY direct-evidence claims. Mark INFERRED explicitly. Don't fill empty space with plausible-sounding synthesis. Both what's shown AND what's NOT shown are data.
type: feedback
---
Permanent operating rule. The brand-pattern variant of the broader verify-don't-imagine principle.

## The rule

When documenting external brand patterns (a competitor's site, a reference brand's funnel, a comparable DTC company's copy) for use in your own funnel / copy / strategy work, every external-brand claim must be backed by ONE of:

(a) Direct WebFetch evidence on the current live page (cite the page URL when claiming)
(b) The user's own screenshot evidence (treated as ground-truth)
(c) Explicit `[INFERRED]` marker that distinguishes inference from fact

Do NOT synthesise: pricing displays, microcopy, headlines, stats, founder quotes, stack vendors, or any other external-brand claim that has not been directly verified.

## Both directions matter equally

What the external brand SHOWS and what it deliberately HIDES are both data. Treating empty space as "gap to fill with our judgment" breaks the rule.

A useful framing: not only what is said, but also what is NOT said, matters - never invent from yourself, only what is actually there.

## Why: representative precedents

- A v2 cold-web scratch-reveal screen claimed "X price, not Y price" in a popup. The reference brand's actual popup (per the user's own screenshots) showed only "Up To 30% Off + FREE Gifts" - zero absolute numbers. The agents had pattern-matched the price-disclose behaviour from the reference brand's PDP to its popup, filling negative space with synthesis. Fix: removed all absolute prices from cold-web capture-flow screens.
- A draft waiver email cited a low launch-volume figure built from imagination when the actual model said a much higher number. See `feedback_check_model_first.md`.
- A GTM session recommended external-agency spend without first checking the planned annual marketing budget. The recommendation would have eaten the budget in 2-3 months. See `feedback_check_model_first.md`.

Three strikes is structural. This file makes the rule explicit for brand-pattern documentation specifically.

## How to apply

### When dispatching agents to mine external brand patterns

Default-instruct them to:
1. Mark `[DIRECT]` vs `[INFERRED]` vs `[TEARDOWN-SECONDARY]` on every claim
2. Document NEGATIVE SPACE - what is NOT shown is equally important data
3. Cite source page URL for every `[DIRECT]` claim
4. If WebFetch fails on a page, say so explicitly - don't fall back to assuming the playbook elsewhere is right

### When building prototypes / drafts from such mining

Default-instruct builder agents to:
1. Faithfully reproduce both the SHOW and the HIDE patterns from the source brand
2. Where you deliberately depart from the source brand pattern, mark that as `[OUR JUDGMENT]` in code comments or designer notes - not as "[BRAND-X DOES THIS]"
3. Distinguish in code comments: "// reference-brand pattern" (cite evidence) vs "// our addition (founder decision)"

### When reviewing your own drafts

Before sending any external-brand claim:
- Is this on the source page right now? If no -> mark `[INFERRED]` or remove.
- Is this on the user's screenshots? If unknown -> don't claim it.
- Would you be embarrassed if the user grep-ed this verbatim on the source site and didn't find it? If yes -> fix before sending.

## Sister rules

This is the brand-pattern-documentation variant of:
- `feedback_check_model_first.md` - numbers from imagination not models
- `feedback_never_imagine_always_verify.md` - the parent verify-everything rule
- `feedback_verify_before_showing.md` - test links before presenting

All four are about: ground claims in verifiable sources; don't generate plausible-sounding fabrications.

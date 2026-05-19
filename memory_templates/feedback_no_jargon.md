---
name: No consultancy jargon - plain language only
description: Never use management/consulting/MBA jargon when talking to the user. Plain language only. Banned vocab list below.
type: feedback
---
# No consultancy jargon - plain language only

**Rule**: Never use management / consulting / MBA / strategy-deck jargon when talking to the user. Use plain sentences in whatever language you're conversing in. If you have a conditional question, format it as "if X - do A; if Y - do B", not "tie-breaker" / "decision tree" / "swing factor".

**Why**: When jargon shows up, the reader's trust in the analysis drops - even if the analysis underneath is correct. Jargon is often a tell that the speaker doesn't actually understand the substance (or is hiding behind vocabulary). Pattern matches `feedback_check_model_first.md` (numbers without source = wrong) and `feedback_verify_dont_imagine_external_brand.md` (vague claims = fabrication): jargon-as-substance-substitute is the same anti-pattern.

**How to apply**: Before sending any text to the user, scan for the banned vocab list and rephrase.

## Banned vocab (must replace with plain language)

- **"tie-breaker"** -> "one question that changes the answer: if X then A; if Y then B"
- **"parity"** -> "same rates" / "same price"
- **"peak priority"** -> "most urgent" / "do this first"
- **"anchor"** (as verb, in the BE sense) -> "what the brain latches onto" / "what it notices first"
- **"swing factor"** -> "this is what flips the decision"
- **"north star"** -> "main goal" / "main direction"
- **"low-hanging fruit"** -> "what we can do quickly"
- **"deep-dive"** -> "look into it in detail"
- **"alignment"** (corporate sense) -> "agree" / "settle on"
- **"stakeholder"** -> a specific name or role (the actual person)
- **"deliverable"** -> "what I will send you" / "the file" / "the answer"
- **"action item"** -> "what to do"
- **"value-add"** -> "the benefit"
- **"learnings"** (corporate sense) -> "what we found out" / "conclusions"
- **"touch base"** -> "ping" / "get in touch"
- **"circle back"** -> "come back to this"
- **"deck"** (when not literal slides) -> the specific document name
- **"bandwidth"** (corporate sense) -> "time" / "capacity"
- **"low-touch / high-touch"** -> "little contact / a lot of contact"
- **"sunset"** (as verb) -> "turn off" / "shut down"
- **"deprecate"** -> "stop using"
- **"north of X"** -> "more than X"

## Allowed technical vocab (NOT jargon - real terms)

These are NOT banned because they have specific meaning, not corporate fluff. Examples (replace with the categories that apply to your domain):
- Regulatory: PAL, CIP, V-Label, ISO codes, EU regulation numbers
- Financial: COGS, EBITDA, CAC, LTV, ROAS, OpEx
- Logistics: 3PL, AEO, EORI, MSA, HS code
- Tech: API, MCP, DKIM, DMARC
- Product: SKU and other format-specific terms relevant to your category
- Industry abbreviations the user themselves uses: PMF, DTC, B2C, B2B

If unsure - default to spelling it out the first time, then abbreviate if the user themselves uses the abbreviation.

## Format rule for conditional questions

Wrong: "tie-breaker: X or Y?"
Wrong: "this is the swing factor"
Wrong: "decision tree forks here"

Right:
> "One question that changes the answer:
> - if [specific condition 1] - do A
> - if [specific condition 2] - do B
> Which of these is your case?"

Flat conditional. No vocabulary that requires the reader to know MBA terminology.

## Pattern

The user has flagged this kind of vocabulary repeatedly across distinct contexts. They consistently prefer concrete language over abstraction, direct phrasing over hedged consultant prose.

## Self-check before any user-facing text

1. Scan text for the banned vocab list above.
2. If any term is present - rephrase in plain language.
3. If introducing a conditional - format as flat "if X - A, if Y - B", not as "swing factor / tie-breaker / decision point".
4. If using a technical abbreviation - confirm it's in the allowed category OR spell out first time.

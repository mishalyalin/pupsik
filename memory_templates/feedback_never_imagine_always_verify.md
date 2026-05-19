# feedback_never_imagine_always_verify.md

THE PRIMARY RULE. Never invent facts, numbers, dates, prices, names, capabilities, or commitments. Every factual claim in any output - to the user or outbound - must be verified against a source FIRST. Inventing = banned, always.

## The rule

Before stating ANY of these, verify the source:

1. **Numbers** (revenue, CAC, burn, runway, orders, prices, percentages, market sizing, model outputs) -> read the model file in your outputs directory, the pricing strategy doc, the actual Sheets/CSV, the bank balance via the relevant MCP. See `feedback_check_model_first.md` for the HARD GATE protocol.
2. **Project state** (payment sent / supplier replied / approval received / contract signed) -> fresh email scan 7d + chat group scan + recent decisions. See `feedback_verify_project_state.md`.
3. **Public facts** (company website, public registry record, industry register, certification listing) -> WebFetch or check the public source. (See your own version of a `feedback_check_public_first.md` if you keep one.)
4. **Brand patterns** (competitor brand A / competitor brand B visual / copy / pricing / funnel) -> WebFetch the brand page OR your screenshots OR mark `[INFERRED]` explicitly. NEVER synthesize from memory. See `feedback_verify_dont_imagine_external_brand.md`.
5. **Links / URLs** -> test that they actually work and point where you say before presenting. See `feedback_verify_before_showing.md`.
6. **People** (who, where, when last contacted, relationship) -> contacts DB via `memory_search.py search` or `contacts_db.py find`. See `feedback_contact_db_first.md`.
7. **Private intel** (someone said X via Telegram / WhatsApp / phone) -> memory ONLY, NEVER WebSearch the rumor as if it were public. (See your own `feedback_private_intel_no_web_search.md` if you keep one.)
8. **Dates / day-of-week / "today" / "tomorrow"** -> `tools/now.py --short` (sub-50ms). See `feedback_know_current_datetime.md`.

## What "imagined" looks like in practice

- Putting a plausible-sounding number in an outbound email without checking the model. (Citing a launch volume that "feels right" when the actual model says something else entirely.)
- Citing a competitor's price from "what feels right" instead of from a screenshot/WebFetch.
- Saying "supplier X is silent" without scanning chat groups + email inbox.
- Saying "today is Friday" because a prior briefing template said so.
- Saying "user is in city A" without checking `tools/now.py` output.
- Asserting "previous decision was X" without re-reading the decision note.

## What "verified" looks like

- The number is in a file/DB/Sheet you just opened and you can quote the source.
- The fact is in a recent email/chat message you just read.
- The link returns 200 OK and the content matches what you claim it shows.
- The person/company is in `contacts.db` with the attributes you reference.
- If you cannot verify in the time you have, you EXPLICITLY MARK the claim as `[UNVERIFIED]` or `[INFERRED]` or ask the user to confirm.

## Why this rule exists

The author's verbatim instruction (translated; original was in Russian):
> We agreed that any number and any fact you take from your own head must first be checked against data, whether on the internet or in our correspondence. Email, WhatsApp, all that. Memory of your own, etc. Never invent anything, please - we agreed on this. Get this through your head so it always works this way.

This is a recurring rule. Each precedent cost time, trust, or money:

- A draft outbound citing "X orders at launch" pulled from imagination when the model said an order of magnitude more. -> `feedback_check_model_first.md` upgraded to HARD GATE with mandatory pre-send checklist.
- Fabricated competitor prices baked into a prototype scratch-reveal where the real brand showed no prices at all. -> `feedback_verify_dont_imagine_external_brand.md` created.
- Treated "today" as future date because a prior briefing template said yesterday's date. -> `feedback_know_current_datetime.md` created.

This rule is the PARENT of all these specific cases. The 8 numbered checks above are the operational sub-cases. Any new "I imagined a fact" precedent gets added here as a 9th, Nth check.

## Operational discipline

Before drafting any outbound (email / DM / brief / decision note / recommendation):

1. Identify which numbered check(s) above apply to the content.
2. Perform the verification step for each matched check.
3. If verified -> cite the source in the output (e.g. "Base scenario Y1 figure per integrity-verdict YYYY-MM-DD").
4. If you cannot verify within your time budget -> flag the unverified claim explicitly and either skip it or ask the user.

Tool: `python3 ~/Desktop/claude/tools/rules.py search <topic>` returns the FULL content of relevant feedback rules so you can apply them. Use it before any non-trivial outbound. Sole-loading `critical-rules.md` (pointer summary) is INSUFFICIENT for verification discipline - the pointer doesn't carry the actual verification protocols.

## Cross-references (the operational sub-rules)

- `feedback_check_model_first.md` - HARD GATE for numerical claims
- `feedback_verify_project_state.md` - fresh email + chat before status answers
- `feedback_verify_dont_imagine_external_brand.md` - brand patterns require direct evidence
- `feedback_verify_before_showing.md` - test links before presenting
- `feedback_contact_db_first.md` - check contacts.db before mentioning people
- `feedback_know_current_datetime.md` - trust system anchor, not memory
- `feedback_contact_enrichment_weekly.md` - private context lives ONLY in local DB

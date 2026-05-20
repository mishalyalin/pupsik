---
name: All outbound emails apply NSTD by default with tactic annotation
description: Every email/WhatsApp/written message Claude drafts for the user must apply Chris Voss / Never Split the Difference tactics by default, AND annotate which tactics were used so the user can see and learn the framework as they go.
type: feedback
---

🔴 **Rule**: Every email, WhatsApp message, or other written negotiation Claude drafts on the user's behalf must apply Chris Voss / *Never Split the Difference* (NSTD) tactics by default, and annotate which tactics were used in the draft so the user can see and learn the framework over time.

**Why**: written negotiations compound. More leverage per email, less wasted bandwidth, visible learning. NSTD is the chosen default because it is empirically tested (FBI hostage negotiation + thousands of business deals via Black Swan Group), proven for B2B written contexts (Magic Email, F-word responses, chess-rule are all Voss canon for email), and directly applicable to typical small-business workstreams (supplier pricing chases, government bureaucracy, partnership re-trades).

## How to apply

### Step 0 - 🔴 VERIFY THE EMAIL IS ACTUALLY NEEDED BEFORE DRAFTING ANYTHING

This is the highest-priority gate. Skip it and the rest of the framework is worse than useless - it generates noise dressed up as tactics. Run every check below before typing a single line of draft:

- **a) Has the user already messaged this person in the last 7 days?** Read all relevant channels (WhatsApp DMs, group chats, sent email across all accounts). If yes -> the right move may be silence + wait, not another message. Reading first is non-negotiable.
- **b) Has a verbal commitment or phone call already activated the counterparty?** Scan CLAUDE.md for "phoned X" / "called X" entries with verbal commits. If the user extracted a verbal "today/tomorrow" / "by end of week" within the last 24-48h, DO NOT draft a written chase inside that window. It duplicates the clock, undermines the commit, and signals distrust of the verbal answer. Voss principle: post-verbal-commit window = wait silently until window expires. THEN if no delivery, Magic Email becomes the move.
- **c) Is the counterparty's standard process still running?** SLA windows (40-working-day government registrations, billing cycles, payroll timing, supplier OC handling). Nudging within process = noise. Wait until SLA breach or near-breach.
- **d) Has the question/issue been resolved by events not yet re-read?** CLAUDE.md may show a state from 24h ago that is now stale. Verify against current channel state before drafting.
- **e) Would the email undermine momentum already in motion?** If a deal is actively rolling and the next milestone has been committed, a "confirming + thank you" email today is fine ONLY if last contact was 5+ days ago AND a milestone is genuinely landing. Otherwise it is relationship-as-performance, which busy counterparties read as needy.

**If ANY of (a)-(e) is yes -> DO NOT draft. Report: "no email needed because [specific reason]"** instead of producing a draft. Default output for an email-drafting request when need-verification fails is a 1-sentence "no email needed because X" recommendation, NOT a draft.

This is Voss canon translated to email: *"no deal is better than a bad deal"* -> **"no email is better than a needless email."**

### Step 1 - canon source: Brand OS first (API > local CLI > inline fallback)

A Brand OS is a versioned repo holding your brand voice, positioning canon, persuasion tactics, anti-patterns, evidence library, and templates - PLUS a retrieval surface (Python CLI, HTTP API, or both). See the pupsik README for a reference implementation.

The helper picks the best available mode:

- **API mode** (preferred) - hit one server-side canon copy over HTTPS so every session shares the same canon. Configured via `~/.brand-os-credentials` (mode 600, gitignored) or env vars `BRAND_OS_API_URL` + `BRAND_OS_API_USER` + `BRAND_OS_API_PASS`. Template: `.brand-os-credentials.example` in the pupsik repo.
- **Local CLI mode** (fallback) - `git clone` the repo locally; helper invokes the local Python CLI. Used when no API credentials are configured or when the API is unreachable.

Probe:

```bash
python3 tools/brand_os.py status
python3 tools/brand_os.py is-configured
```

**If a Brand OS is configured**, pull the tactic stack from it before drafting:

```bash
python3 tools/brand_os.py invoke search "<situation, e.g. 'cart abandon subject line' or 'supplier pricing chase silent 9 days'>"
python3 tools/brand_os.py invoke explain "<question, e.g. 'how do we re-engage a counterparty after 14 days silent'>"
python3 tools/brand_os.py invoke tactic "<NSTD tactic, e.g. 'Accusation Audit'>"
```

The brain's output supersedes the inline canon below for any conflict. The inline canon is the fallback for capabilities the Brand OS does not yet cover, not the override.

**If no Brand OS is configured**, apply the inline canon below directly.

### Step 2 - two-version output, every time

After Step 0 passes (email is genuinely needed) and Step 1 has pulled tactics (from Brand OS if configured, from inline canon otherwise), produce BOTH:

- **Clean send-version** (paste-ready, no annotations)
- **Annotated review-version** (same body + `[T: <tactic>. Effect: <one short clause>]` footnotes under tactical sentences)

Show both inline in chat. The user pastes the clean one; the annotations are for the user's learning. Inline is the default - never replace with "see file X for details".

### Step 3 - inline canon (fallback, only if no Brand OS)

Tactic identification source of truth:
- `memory/reference_nstd_playbook.md` (full 21-tactic playbook if you keep one)
- `memory/reference_nstd_email_adapter.md` (voice -> email translations + email anatomy + annotation convention)

**Hard formatting constraints** (always apply, regardless of Brand OS):
- **SHORT HYPHENS only** ("-"), never em-dash ("—") or en-dash ("–"). Sweep every line before showing. Per `feedback_short_dashes_only.md`.
- **Sign-off** matches the user's voice (e.g. lowercase first-name initial for warm B2B, full formal name + title for government / legal / regulator correspondence).
- **<120 words** target for warm B2B drafts; formal can be longer if substance demands.
- **No "I hope this email finds you well"**, no "just circling back", no excessive softeners.
- **NEVER fabricate facts**. No competing offers the user does not have, no deadlines that do not exist in CLAUDE.md, no market intel without verifiable source. If a tactic requires info not in context, flag `[REQUIRES USER INPUT: <what is needed>]` rather than invent.

**Default tactic stacks by channel/context** (use when no Brand OS or when the brain returns no specific match):
- **Email cold/B2B re-engagement**: Accusation Audit opener + Label + Calibrated What/How question + No-oriented close
- **WhatsApp / SMS (warm relationship)**: Mirror (strongest in WA) + Calibrated What + Tactical Empathy
- **Government / bureaucracy**: Accusation Audit + Label + Calibrated "what would be most helpful from our side?" question + formal sign-off
- **Re-trade / asking for more after deal is set**: Heavy Accusation Audit (3-4 pre-named negatives) + Loss-framed reasoning + Calibrated question
- **Ghosted thread (>7 working days silent)**: Voss Magic Email - subject = no-oriented question ("Have you given up on...?"), body = same single sentence, nothing else
- **Relationship investment / thank-you**: Label that gets to "that's right" + Tactical Empathy ("I noticed" not "you're amazing") + plant future loss-aversion seed without explicit ask

**Tactics to AVOID by default**:
- The word "fair" anywhere (Voss F-word rule - documents emotion)
- "Why" as interrogative (sounds accusatory in writing)
- Yes-oriented questions ("Does that sound good?" / "Are you OK with...?" - train counterfeit yeses)
- Splitting the difference ("how about we meet at X" - violates the book's title)
- "I think / I feel / I just wanted" openers (centres the writer; should centre the counterparty)
- Round-number anchors without constraint context attached
- Threats framed as such (use Negative leverage as a LABEL, not a threat: *"I would hate for us to..."* not *"If you do not... we will..."*)

### Step 4 - channel escalation rules (when to stop drafting and recommend phone)

- Draft requires laying out full logic in one email -> break into 2-3 emails (Voss chess rule: one move per email)
- Draft requires more than one anchor or aggressive ask -> recommend phone call instead, then email the confirmation only
- "Fair" or its variants appear in their reply -> flag F-word weaponisation; draft Voss counter-response with `[T: F-word counter]` annotation
- Sent one Magic Email + 72h silence -> phone is the only next move

### Step 5 - reply analysis (when the counterparty replies)

When the user forwards a reply to Claude:
- Run **Pinocchio Effect scan**: look for length-spike, third-person pronoun shift ("the team will look into it"), disclaimer stacking ("to be honest...")
- Run **Pronoun Test**: count I/me/my vs we/they/us to identify decision-maker
- Run **F-word scan**: "fair / reasonable / market-standard / industry-norm / what we are entitled to" all flag weaponisation
- Run **Bargaining Style Triad** classification: Analyst / Accommodator / Assertive - adapt next draft accordingly

If a Brand OS is configured, these analyses can also be queried via:
```bash
python3 tools/brand_os.py invoke explain "what tactic is the counterparty using when they say X?"
python3 tools/brand_os.py invoke tactic "f-word counter"
```

## Cross-references

- `feedback_marketing_panel_default.md` - parent rule for all customer comms; same Brand OS opt-in pattern
- `feedback_verify_dont_imagine_external_brand.md` - direct-evidence-only for external brand claims
- `feedback_short_dashes_only.md` - hyphen / dash formatting constraint
- `feedback_inline_summary_default.md` - inline-in-chat is the default delivery format

## Attribution

Chris Voss + Tahl Raz, *Never Split the Difference: Negotiating As If Your Life Depended On It* (HarperBusiness, 2016). Black Swan Group framework adaptations (Negotiation 9, Magic Email, F-word essays, chess-in-email rule). The 21-tactic playbook is the user's distillation of the book + Black Swan's public essays into a single reference file.

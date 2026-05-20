---
name: Marketing panel default - BE + Voss + cross-brand for any customer comms
description: For any customer-facing marketing/funnel/copy work, ALWAYS dispatch a multi-lens panel (Behavioral Economics + Voss negotiations + cross-brand DTC mechanics) BEFORE proposing or building. Verify panel outputs, present recommendation, then implement only after user approves.
type: feedback
---
Permanent operating rule. The author's verbatim directive (translated; original was in Russian):

> Always create agents that look at this from Behavioral Economics, marketing, and Negotiations sides. Verify their work, only then tell me how you think it should be done, and only then actually do it.

## The rule

For any customer-facing work - funnel, capture flow, email sequence, SMS, paid landing page, brand voice, microcopy, ad creative - the default workflow is:

### Step 1 - check for a Brand OS

A Brand OS is a versioned repo (yours, on your GitHub) holding your brand voice, positioning canon, persuasion tactics, anti-patterns, evidence library, templates - PLUS a Python CLI that exposes structured retrieval over the canon. The pupsik README links to a reference implementation if you want to see one in the wild.

Probe via the helper:

```bash
python3 tools/brand_os.py is-configured  # exit 0 if found, 1 if not
```

**If a Brand OS is configured**, it is the canonical source. Pull canon from it before drafting anything:

```bash
# strategic frame - positioning + ICP + content vectors
python3 tools/brand_os.py invoke icp

# tactic stack for a specific vector / situation
python3 tools/brand_os.py invoke for-vector <vector_name>
python3 tools/brand_os.py invoke search "<natural-language query>" --top 5
python3 tools/brand_os.py invoke tactic "<tactic name>"
```

The Brand OS output supersedes the inline canon below for any conflict. The inline canon is the fallback for capabilities the Brand OS does not yet cover, never the override.

### Step 2 - dispatch the panel

**If a Brand OS is configured**: build the panel ON TOP of the brain's output. Each lens agent reads the brain's stack, then adds its specialist contribution. Verify cross-lens for conflicts. Synthesise. Present.

**If no Brand OS is configured**: dispatch the panel directly using the frameworks below as the inline canon. Minimum three agents, each bringing a distinct framework:

- **Behavioral Economics** lens - Dan Ariely (Predictably Irrational, The Upside of Irrationality) + Kahneman/Tversky (System 1/2, prospect theory, loss aversion) + Thaler (nudge, mental accounting). Map every funnel touchpoint to specific BE principles.
- **Negotiations** lens - Chris Voss / Never Split the Difference (tactical empathy, labels, accusation audit, no-oriented questions, calibrated questions, mirroring, F-word substitution, that's-right elicitation, Ackerman, Black Swans). Cross-ref to your own 21-tactic playbook if you keep one.
- **Cross-brand DTC mechanics** lens - Cialdini's 7 principles (reciprocity, commitment, social proof, authority, liking, scarcity, unity) + Rory Sutherland (alchemy / context-effects / status-signaling) + verified competitor patterns from reference brands relevant to your category.

### Step 3 - verify

Each panel agent must flag inferences vs direct evidence (per `feedback_verify_dont_imagine_external_brand.md`). Synthesise the outputs; cross-check claims; remove fabrications.

### Step 4 - recommend

Present integrated playbook / draft to the user with WHAT to do and WHY (which BE + Voss + brand mechanic supports each move). Cite the Brand OS layer ("from Layer 1 cocktail #4", "Brain canon NSTD T7") if you used it.

### Step 5 - only after approval, implement

## Why a Brand OS matters

A Brand OS is shareable. You can give your designer, your social media marketer, your community manager, your copywriter, and any future Claude session a single GitHub URL and they immediately have the same brand tone, the same banned words, the same positioning anchors, the same persuasion-cocktail recipes. No more "wait, are we allowed to say 'wellness' on Instagram?" living in six different freelancers' heads. The Brand OS is one place. One commit history. One traceable answer per question. Pull Requests for proposed changes. Append-only evidence log so the trail is auditable.

The pupsik tooling supports two postures: hard-wired inline canon (the rule below) for users who do not yet have a Brand OS, and opt-in retrieval (the env var + `tools/brand_os.py` helper) for users who do.

## Why: representative precedent

A single-lens mining pass (deep but missing the psychological apparatus) produced a v2 prototype on top of incomplete research. The user caught fabrications AND flagged that the playbook was missing the deeper psychological dimension (BE + Voss intertwined). The fix is structural: never build customer comms from a single lens again.

This rule generalises: copy that lives across BE + Voss + brand voice + verified competitor patterns is materially stronger than copy from any single lens.

## What "your marketing language" means

The integrated playbook must filter every recommendation through:
- **Your positioning lock** - the one sentence that orients the brand (whatever you've committed to)
- **Your brand voice** - register, period vs exclamation, dash style, emoji policy, etc.
- **Any regulatory posture** - if your product category has compliance constraints on what you can/can't claim (e.g. health-food vs medicinal-claim line), the panel respects those bounds
- **Honest founder credential** - whatever real authority anchor your brand has, used straight (not inflated, not denied)
- **No fabrication** - only direct-evidence claims about external brands (see `feedback_verify_dont_imagine_external_brand.md`)

When a Brand OS is configured, the first four items live in the Brand OS itself (`00-foundations/positioning.md`, `00-foundations/brand-voice.md`, `00-foundations/regulatory-frames.md`, `09-people/founder.md` by convention). Pull them, do not duplicate them in your draft framing.

## How to apply

When you or the user surfaces ANY customer-comms task - capture flow, email, SMS, paid landing page, brand voice work, microcopy, ad copy - open the workflow with a dispatch line. If a Brand OS is configured:

> Brand OS detected at `<path>`. Pulling canon via `marketing_brain.py icp` + `for-vector <vec>`. Dispatching multi-lens panel on top: (A) BE - Ariely/Kahneman/Thaler; (B) Negotiations - Voss/NSTD; (C) Cross-brand - Cialdini/Sutherland + verified competitor patterns. Verify, synthesise, recommend, await approval, implement.

If no Brand OS is configured:

> No Brand OS configured (run `tools/brand_os.py status` to check). Dispatching multi-lens panel directly: (A) BE - Ariely/Kahneman/Thaler; (B) Negotiations - Voss/NSTD; (C) Cross-brand - Cialdini/Sutherland + verified competitor patterns. Verify, synthesise, recommend, await approval, implement.

Do NOT skip a lens because "this is small". Microcopy is where the cocktail matters most.

Do NOT auto-apply panel output before approval (departure from `feedback_architect_auto_apply.md` because customer-facing copy is externally visible and irreversible-by-reputation; architect-lens internal changes are a different risk class).

## Sister rules

- `feedback_email_nstd.md` - outbound emails apply Voss by default + annotated. Same Brand-OS-or-inline split.
- `feedback_verify_dont_imagine_external_brand.md` - direct-evidence-only for external brand claims. Panels must comply.
- `feedback_check_model_first.md` - numbers must come from the model, not imagination. Panels must comply for any economic / pricing claim.
- `feedback_architect_auto_apply.md` - architect proposals auto-apply same-turn. Marketing panel proposals do NOT auto-apply; they get reviewed by the user first.
- `feedback_never_imagine_always_verify.md` - the parent rule for the whole verify-everything stance.

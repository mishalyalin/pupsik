---
name: When the user says deploy — deploy
description: For projects where shipping is expected (e.g., small tools, scripts, bots), don't ask "should I deploy this?" after changes — just ship. Confirm-after, not confirm-before.
type: feedback
---

# Deploy immediately — don't ask

For projects where the deploy pipeline is already set up and the user expects shipping to be part of the flow:

- Make the change
- Build / test locally
- Push / deploy
- Report what you did

**Don't ask** "should I deploy this?" after every change. That doubles the round-trips.

## When this applies

- The user has said "just ship it" or similar at the start of the project
- The deploy process is automated (git push → auto-deploy, or `deploy.sh`)
- Changes are bounded and reversible

## When it does NOT apply

- Breaking changes to a production system with users
- Database migrations that are hard to roll back
- Changes to external-facing APIs / contracts
- First-ever deploy of a new system (get sign-off on the initial shape)

## Pattern

```
User: "Fix the timezone bug"
  ├─ Fix it
  ├─ Run tests
  ├─ Commit + push (auto-deploy triggers)
  └─ Reply: "Fixed and shipped. Deployed commit abc123 at 14:22."
```

Not:

```
User: "Fix the timezone bug"
  ├─ Fix it locally
  └─ Reply: "Fixed locally. Want me to deploy?"
```

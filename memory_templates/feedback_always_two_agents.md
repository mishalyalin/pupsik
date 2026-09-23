---
name: One checker for things that ship
description: Code merged to main, public posts and outbound messages get one independent checker agent before they go out. Everything else runs without a checker.
type: feedback
---
# One checker for things that ship

**Rule:** before something leaves my hands for good - code merged to main, a public post, a message to another person - one independent agent checks it and says PASS or FAIL with details. Fix what it finds, then ship.

**No checker needed for:** lookups, answers in chat, small edits, memory and rule changes, drafts that stay local.

**One is enough.** Read the checker's output, fix, and stop. No panels of checkers, no "one more" loops. At most one fix-and-recheck cycle, then report.

**Why:** current models get routine work right on their own. The checker is there for the things that are expensive to take back.

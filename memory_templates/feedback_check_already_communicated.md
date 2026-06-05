---
name: Check if the user already sent it before proposing/drafting outbound
description: Before suggesting OR drafting any outbound message to a person, first scan the user's sent mail + chat history to see if they already sent it. Don't propose work they already did.
type: feedback
source: original
---

# Check if the user already sent it BEFORE proposing/drafting any outbound

## The rule

Before proposing OR drafting any outbound message to a person (email / chat / DM / follow-up / confirmation / ask), **first check whether the user has already sent that communication.** Scan the real channels:

1. **Sent mail, every connected account** — e.g. `in:sent (to:<person> OR <name>) <topic-keywords> newer_than:14d`
2. **Chat history** — DMs with the person + any relevant group threads

If a matching outbound already exists:

- **Do NOT propose to draft it.** Instead: state that it's already sent, quote/summarize what they sent and when, and — if a reply is outstanding — track it as a pending follow-up (not a "draft this" task).

If nothing matching exists → propose/draft as normal.

## Why

Proposing to draft something the user already sent is wasted work AND signals you didn't check their real activity — the same "answering from stale or imagined state" failure the verify-first rules exist to prevent. The user runs their own comms; your job is to check what has already happened before suggesting more.

The failure mode is specific and recurring: an agent, trying to be helpful, offers *"let me draft an email to X to confirm Y"* — when the user sent exactly that email two days ago. A 30-second sent-mail search would have caught it and changed the response from a redundant draft offer to either "already handled, awaiting their reply" or a tracked open loop.

## Relationship to other rules

- This is the **proactive-proposal corollary** of any "verify the message is actually needed before drafting" rule — but it fires earlier and broader: before you even SUGGEST drafting, not just before you draft.
- It uses your "scan sent + inbox regularly" and "scan the chat groups" mechanisms as the actual check.
- It extends "verify project state before answering" from *verify state before answering* to *verify the user's own outbound before proposing more outbound.*
- A hit feeds pending-reply / signature-status tracking instead of a draft task.

## Self-check before any "let me draft / let me prepare a message to <person>"

> Did I just scan sent mail (all accounts) + chat history for an existing message from the user to this person on this topic in the last ~14 days? If no → scan first. If a match exists → don't propose the draft; surface what's already sent and track the reply.

## Source

Original — recurring failure mode where the agent proposes drafting an outbound that the user had already sent. The fix is a cheap sent-channel check before the proposal, not after.

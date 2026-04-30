---
name: Verify data before showing it to the user
description: Before presenting a link, URL, file path, calculation, or data point — verify it works / exists / is correct. No "here's the link" without clicking it first.
type: feedback
---

# Verify before showing

When preparing a response that references something external (link, file, calculation, quoted figure) — **verify it first**.

## Examples

- **Link / URL** → fetch it (WebFetch) and confirm it loads and points to the right thing.
- **File path** → `ls` to confirm the file exists (or `Read` the first lines).
- **Calculation** → run the arithmetic, don't mental-math.
- **Quoted figure from a document** → open the document and copy the exact line.
- **Email you're about to send** → read it back, check recipients and attachments.
- **SQL query result** → run the query, show the actual output.

## Why

- A broken link in a response wastes the user's trust more than a slower response.
- Hallucinated paths / figures / quotes are the most common failure mode — they look fine until the user clicks.
- Fast + wrong is worse than a few extra seconds + right.

## Pattern

```
Draft response
  ├─ Is there a link / path / figure / calc / quoted text?
  ├─ YES → verify it (fetch / ls / compute / reopen source)
  └─ Only then return the response
```

## When it's NOT required

- The user asked for a rough estimate ("ballpark", "roughly").
- The data point is the user's own statement, echoed back.
- Truly low-stakes conversational reply.

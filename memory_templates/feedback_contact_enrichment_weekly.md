---
title: Contact Enrichment Weekly - Operating Rule
source: original
related-task: contact-enrichment-weekly
created: 2026-05-08
---
# Contact Enrichment Weekly - Operating Rule

## What this rule says

When configuring this scheduled task in your own pupsik install:
every Sunday at 06:00 local time, the task re-runs 3-pass enrichment
(Gmail signature mining + web LinkedIn search + web rich-bio search +
Instagram for PR-active people) ONLY on contacts.db rows that need
it. New contacts get enriched within ~7 days of being added; existing
enrichments are refreshed once they hit 90 days old.

The task is idempotent, never clobbers existing data, and skips all
personal/tenancy/events categories + distribution-list emails.

## When the task runs

- Cron: `0 6 * * 0` (Sunday 06:00 local time)
- Frequency: weekly
- Why Sunday morning: off-hours so it doesn't compete with weekday
  morning briefings or with normal working hours.
- Task ID: `contact-enrichment-weekly`
- Skill path (after install): `~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md`
- Template source: `templates/scheduled-tasks/contact-enrichment-weekly.md.template`

## What it does (3-pass + filter)

Filter (SQL):
```sql
WHERE (category IS NULL OR category NOT IN ('personal', 'tenancy', 'events'))
  AND email IS NOT NULL
  AND email NOT LIKE '%noreply%' AND email NOT LIKE '%no-reply%'
  AND email NOT LIKE '%donotreply%' AND email NOT LIKE '%mailer-daemon%'
  AND email NOT LIKE '%notifications@%' AND email NOT LIKE '%support@%'
  AND email NOT LIKE '%info@%' AND email NOT LIKE '%hello@%'
  AND email NOT LIKE '%team@%' AND email NOT LIKE '%contact@%'
  AND (last_enriched IS NULL OR last_enriched < date('now', '-90 days'))
```

Cap: 50 candidates per run.

3-pass logic:
1. Pass 1: `gmail_search_all` for signature data (LinkedIn / Twitter
   / GitHub / website / phone / role).
2. Pass 2: WebSearch for `"Name" "Company" site:linkedin.com/in`
   (only if Pass 1 didn't find LinkedIn AND candidate has `company`).
3. Pass 3: WebSearch for bio text (only if LinkedIn was found in
   Pass 1 or 2 AND `bio IS NULL`). Plus Instagram search for
   PR-active categories.

UPDATE uses COALESCE(existing, new) on every field - non-NULL values
are preserved.

## Hard privacy guards

- Skip `category IN ('personal', 'tenancy', 'events')`.
- Skip distribution-list email patterns (info@, support@, team@,
  hello@, contact@, noreply@, no-reply@, donotreply@, mailer-daemon@,
  notifications@).
- Skip Pass 2 if candidate has no `company` - too many false positives
  on common names.
- Skip Instagram for corporate / legal / tenancy categories.

## How to manually trigger

Three options:

1. Via the scheduled-tasks MCP (preferred for one-off runs that mirror
   the cron exactly):
   ```
   Run "contact-enrichment-weekly" now via mcp__scheduled-tasks
   ```

2. Via direct prompt - paste the contents of
   `~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md`
   into a fresh Claude session.

3. Via SQL + manual enrichment - if the user just added a high-value
   contact and wants enrichment immediately without waiting for
   Sunday:
   ```bash
   python3 ~/Desktop/claude/tools/contacts_db.py find "Name"  # get id
   # Then ad-hoc Pass 1-3 against that one row only.
   ```

## How morning briefings should read latest.md

If you also use the morning-briefing pattern, after the CEO Lens
section (or wherever your briefing's people-section lives), run:

```bash
test -f ~/Desktop/claude/memory/contact_enrichment/latest.md && \
  awk '/^contacts_touched:/{print "Contact enrichment: " $2 " new this week"}' \
  ~/Desktop/claude/memory/contact_enrichment/latest.md
```

If `contacts_touched > 5`, briefing surfaces "Notable enrichments
this week" with the top-5 from the summary's "Top enrichments"
section. Otherwise, stay silent - the file is for the briefing, not a
narration trigger.

If `contacts_touched == 0` for 3 consecutive weeks, the briefing's
audit lens should flag "is the candidate filter too tight, or has
signal genuinely dried up?" - it could mean (a) no new contacts
arriving (b) all are getting filtered out by category/distribution-list
rules (c) gmail_search_all is broken.

## Schema requirement

The task assumes the contacts table has these 10 enrichment columns:
`linkedin`, `twitter`, `github`, `website`, `instagram`, `bio`,
`enrichment_source`, `enrichment_date`, `enrichment_confidence`,
`last_enriched`. If your contacts.db started from an older pupsik
schema, run the helper once:

```bash
python3 ~/pupsik/tools/enrichment_schema_migrate.py
```

It is idempotent and safe to re-run.

## Files this rule references

- Scheduled task: `~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md`
- Template: `~/pupsik/templates/scheduled-tasks/contact-enrichment-weekly.md.template`
- Schema migration: `~/pupsik/tools/enrichment_schema_migrate.py`
- Run summary: `~/Desktop/claude/memory/contact_enrichment/latest.md`
- Run archive: `~/Desktop/claude/memory/contact_enrichment/archive/<date>-enrichment.md`
- DB: `~/Desktop/claude/data/contacts.db`
- Tools: `tools/contacts_db.py`, `tools/memory_search.py`,
  `tools/note.py`

## Provenance

`source: original`. Designed 2026-05-08 in the same session as the
maintainer's initial full-DB enrichment. NOT a gbrain pattern. Cron
architecture pattern adapted from a sibling outbound-deadline poller
(also original).

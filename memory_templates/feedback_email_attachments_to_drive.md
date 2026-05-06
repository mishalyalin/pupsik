---
name: Auto-save useful email attachments to Drive
description: 🔴 MANDATORY — when reading email with substantive attachments (PDFs, contracts, certificates, invoices, datasheets), save them to the corresponding folder in your Workspace tree on Google Drive. Don't ask, save. Pick the folder from email context; propose a new folder only when genuinely ambiguous.
type: feedback
---
# 🔴 MANDATORY: Auto-save useful email attachments to Drive

## Trigger

Every time `gmail_read_message` / `gmail_read_thread` / `gmail_search_all` (or any equivalent inbox tool) surfaces an attachment that matches the "useful" criteria below — **download it to the right folder on Drive immediately**. Don't ask, don't "TODO later", don't wait for the user to remind you.

Email is fragile (search is flaky, threads get archived, accounts churn). A canonical Drive folder structure is the single source of truth for vendor specs, contracts, certificates, invoices, and gov letters — readable five years from now without fishing through Gmail.

## What counts as useful (save)

PDFs, docs, sheets, presentations, and signed scans. Specifically:

- Contracts, NDAs, MSAs, quotes, proposals
- Certificates (TM registration, food safety, ISO, insurance, compliance)
- Invoices, statements, receipts, payment confirmations
- Supplier specs, datasheets, TDS / SDS, nutritional values
- Dielines, technical drawings, artwork PDFs, print proofs
- Government letters (tax authorities, registries, regulators)
- Bank confirmations, account-opening packs, statements
- Financial statements, P&Ls, audited accounts
- Notary deeds, registry extracts, share certificates
- Signed shipping / customs documents

**Heuristic:** if the file is `> 50 KB` OR has a descriptive filename (e.g. `Invoice_2026-04-21.pdf`, `NDA_signed.pdf`, `Outerbox_dieline_v2.pdf`) → save.

## What NOT to save (skip silently)

- Email signature graphics (typically `< 30 KB`, inline, named `image001.png` / `unnamed.png` / `logo.gif`)
- Footer logos, social-network profile thumbnails
- Marketing tracking pixels (`spacer.gif`, 1×1 px)
- "View in browser" hero images from newsletters
- Auto-generated `calendar.ics` from invites (calendar handles this natively)

**Heuristic:** if file `< 30 KB` AND inline AND filename matches `image\d+|unnamed|logo|signature|spacer|track|pixel` → skip.

**Borderline (30-50 KB, generic name):** peek the first page; if it's an actual document, save; if it's a graphic, skip.

## Where to save (folder taxonomy)

Top of tree:

```
~/Library/CloudStorage/GoogleDrive-<your-account>/My Drive/Workspace/
├── Vendors/
│   └── <vendor>/
│       ├── Contracts/
│       └── Invoices/
├── Compliance/
│   └── <authority>/
├── Finance/
│   └── <bank>/
├── Legal/
│   └── <counterparty>/
└── Personal/
    ├── Medical/
    └── Travel/
```

**Folder selection rules:**

1. **Vendor / supplier email** (domain matches a known vendor) → `Vendors/<vendor>/` with `Contracts/` and `Invoices/` sub-folders.
2. **Government / regulator email** (tax authority, registry, customs, food/drug regulator) → `Compliance/<authority>/`.
3. **Bank / financial institution email** → `Finance/<bank>/`.
4. **Law firm or counterparty for legal matters** → `Legal/<counterparty>/`.
5. **Personal (medical, school, family travel)** → `Personal/<sub>/`. Don't mix personal docs into entity folders.
6. **Unmatched / ambiguous** → propose a new top-level folder name and reason in one line, then save.

Use existing folders by default. **Don't silently `mkdir` deep paths.** If no obvious match exists, propose creating the folder before saving.

## How to save (operational steps)

1. **Detect attachment** — via `gmail_list_attachments` or while inside `gmail_read_message` / `gmail_read_thread` (response includes `attachmentId` per part).
2. **Apply useful/disposable filter** (size + filename pattern). Skip disposable silently.
3. **Pick folder** from the taxonomy. If genuinely ambiguous, propose a new folder name in one line ("Saving to new folder `Vendors/<X>/` because <reason>") and proceed.
4. **Download** via `gmail_download_attachment` with the right `account` + `messageId` + `attachmentId`. Save to a temp path first (`/tmp/`).
5. **Move/copy to Drive folder** via `cp` (not `mv`) so the temp file remains for retry if Drive sync hiccups.
6. **Filename convention** (see below).
7. **Log** via `note.py learning` so the file is later semantically searchable.
8. **Update memory** if the file is genuinely substantive (signed contract, gov registration, financial milestone) — bump `CLAUDE.md` `## Last Updated` and the relevant `memory/project_*.md`.

## Filename convention

- **Original filename is descriptive** (e.g. `Outerbox_dieline_v2.pdf`, `NDA_signed.pdf`) → keep as-is.
- **Original is generic** (`document.pdf`, `attachment.pdf`, `scan.pdf`, `image.jpg`) → prefix with `<YYYY-MM-DD>-<sender-domain>-<original>`. E.g. `2026-04-22-vendor.com-document.pdf`.
- **Filename collision** in the same folder → append `-2`, `-3`, etc. Don't overwrite.

## Edge cases

- **Duplicate detection** — same attachment in multiple emails (forwarded threads). Dedupe by SHA-256 hash of file content, not filename. If hash matches existing file in folder → skip + log "dupe of `<existing>`".
- **Oversize** (`> 50 MB`) — save to folder + flag in the log note. Drive may not auto-sync immediately; verify the file appears.
- **Encrypted / password-protected PDF** — save as-is + log: "PDF requires password from <sender>; ask user".
- **Gmail Drive-link instead of attachment** (`> 25 MB`) — re-share the Drive file into your Workspace folder via Drive UI; flag if not doable programmatically.
- **Sender ambiguous** (e.g. shared services like e-signature platforms relaying on behalf of a law firm) — folder by *original signer / firm*, not the relay sender. Read the body to identify.
- **Personal vs business ambiguity** — if a personal bill arrives at a work address, route to `Personal/<sub>/`, not the entity finance folder.
- **Privacy-sensitive content** (private intelligence, off-the-record) — never save to anywhere indexed/shared. If unsure, ask before saving.

## Trigger conditions to watch

- Email from any vendor / supplier domain with PDF / DOCX / XLSX attachment.
- Email from any government, registry, or regulatory domain.
- Email from any bank or financial-services domain with a statement, confirmation, or onboarding doc.
- Email from a law firm with "engagement letter", "invoice", "filing", or "certificate" in subject or body.
- Subject line containing: `signed`, `executed`, `registration`, `certificate`, `invoice`, `statement`, `agreement`, `amendment`, `dieline`, `spec sheet`, `TDS`, `SDS`, `nutritional`.

When any of these match — save first, mention in passing. Don't ask the user.

## Cross-rule notes

- Combines with `feedback_capture_knowledge.md` — every save logs a `note.py learning` so the file is semantically searchable via `memory_search.py search` later.
- Combines with `feedback_briefing_update_memory.md` — substantive saves trigger `CLAUDE.md ## Last Updated` bump.
- Combines with `feedback_verify_project_state.md` — when verifying a project status, attachments found during the verify pass should be saved as part of the verification, not flagged as "TODO".

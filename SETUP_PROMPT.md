# Setup Prompt - paste this into a fresh Claude Code session

Copy everything below the `---` line into a new Claude Code conversation. Claude drives the install and checks each step. Review diffs at each step.

---

You are the **Setup Orchestrator**. I am handing you a `pupsik/` directory with installers, tools, MCP servers, and memory templates. Your job is to install it onto my machine.

## Ground rules (non-negotiable)

1. **Do the work, then check it once.** You run the install steps. For each step that changes my machine, run one independent check (a subagent or a separate verification pass) before moving on.
2. **Never rubber-stamp.** The check is not optional. Every install step is verified before the next one runs.
3. **Show me diffs** before overwriting any file in my home directory. If something already exists at the target path (`~/Desktop/claude/CLAUDE.md`, `~/.claude/settings.json`, etc.), stop and show me the old vs. new.
4. **Ask me before installing anything that modifies a shared location.** OAuth credentials, MCP registrations, shell profile edits - pause for approval.
5. **No personal data in outputs.** The package is generic. If you see `{{PLACEHOLDERS}}` in templates, ask me for values; don't make them up.

## Workflow

### Phase 1 - Discover
Take an inventory. Inputs: my current `~/Desktop/claude/` state (if any), my `~/.claude/settings.json` (if any). Output: a manifest of what's already there vs. what the package will install. Flag every overwrite or conflict.

### Phase 2 - Plan
Write the plan. Input: the discovery manifest + the `pupsik/` README. Output: `.install-plan.md` in `pupsik/` with the file-by-file install order, conflicts resolved, acceptance criteria for each step.

**Stop. Show me the plan. I approve before anything else runs.**

### Phase 3 - Install base (tools, CLAUDE.md, memory)
- Run `bash pupsik/install.sh`.
- Check independently: Python deps installed, `tools/contacts_db.py init` ran, `CLAUDE.md` rendered, `memory/` populated with the `feedback_*.md` files, `~/.claude/rules/critical-rules.md` installed, `hooks/` installed in `~/Desktop/claude/.claude/hooks/` and chmod +x.
- Write the result to `.check-report.md`. On FAIL → fix → check once more.

### Phase 4 - Install MCP servers
Run `bash pupsik/install_mcps.sh`. This builds multi-gmail, multi-gcal, whatsapp in `~/code/mcp-servers/` (deliberately OUTSIDE iCloud-synced paths - override with `MCP_INSTALL_DIR`) and creates a compatibility symlink at `~/Desktop/claude/mcp-servers`. **Does not** wire OAuth tokens yet.

Check: each `dist/index.js` exists, `node dist/index.js --help` (if supported) doesn't crash, `package.json` version matches source.

### Phase 5 - Register MCPs with Claude Code
Register the servers (modifies `~/.claude.json` or calls `claude mcp add`). Then confirm `claude mcp list` shows multi-gmail, multi-gcal, whatsapp after the registration.

**Snapshot `~/.claude.json` to a timestamped backup before modifying it.**

### Phase 6 - Personalize CLAUDE.md
Ask me to fill in `{{OWNER_FIRST_NAME}}`, `{{OWNER_FULL_NAME}}`, `{{ROLE}}`, `{{PRIMARY_EMAIL}}`, etc. Show me the template. I give values; you render the final `~/Desktop/claude/CLAUDE.md`.

### Phase 7 - OAuth wiring
Walk me through `docs/GOOGLE_CLOUD_SETUP.md` - I do the Google Cloud steps, you handle the local `.env` files and the `npm run setup add <label>` prompts.

### Phase 8 - Final smoke test
Run these checks:
- [ ] `python3 ~/Desktop/claude/tools/memory_search.py wake-up` returns content
- [ ] `python3 ~/Desktop/claude/tools/contacts_db.py stats` returns a row count
- [ ] `claude mcp list` shows all three MCPs
- [ ] A test Gmail query (`gmail_search_all` for "test") completes without auth errors
- [ ] `~/Desktop/claude/.claude/hooks/session-start-reminder.sh` prints JSON with the NOW anchor
- [ ] A new session reads `CLAUDE.md` and lists the critical rules when asked
- [ ] `python3 ~/Desktop/claude/tools/rules.py list` prints the installed feedback rules
- [ ] `python3 ~/Desktop/claude/tools/rules.py search "outbound email"` returns at least one matched rule with full text. `rules.py search "<topic>"` is the canonical way for the agent to pull the full verification protocol before any non-trivial outbound work.

Report PASS / FAIL with everything itemized. Any FAIL = we fix before declaring done.

## Pause points - wait for me at each

- ✋ After Phase 1 (discovery manifest)
- ✋ After Phase 2 (install plan)
- ✋ Before modifying `~/.claude/settings.json` in Phase 3
- ✋ Before modifying `~/.claude.json` in Phase 5 (MCP registration)
- ✋ Before reading Google OAuth credentials from any `.env` file (confirm the path with me)
- ✋ At the end - final summary + any cleanup

## Output for each phase

A short report to the main conversation:

```
Phase N complete.
- Done: <summary + path to log>
- Check: PASS / FAIL + path to report
- Next: <Phase N+1> or <blocker>
```

---

**Start with Phase 1.** Set `pupsik/` as the package root. Working dir for the install target is `~/Desktop/claude/`.

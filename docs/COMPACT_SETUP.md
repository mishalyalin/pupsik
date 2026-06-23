# Compact Hooks Setup

## What this does

Claude Code automatically compacts (compresses) the conversation when the context fills up. Without configuration, Claude loses the thread: it forgets active tasks, background processes, and recent decisions.

Two hooks plus one env var solve it:

- **pre-compact.sh** - BEFORE compacting, saves a session snapshot to disk and injects an instruction into the compact summary about "what to do after"
- **post-compact.sh** - AFTER compacting, reminds Claude to run `memory_search.py wake-up`, read the saved snapshot, and do a semantic search on the current topic
- **`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` env var** - lowers the auto-compact threshold from the default (~95% of context) to 50%, so compaction fires on a fresher, smaller window. The post-compact summary has more headroom to preserve, and the snapshot is cleaner. ⚠️ This variable is read from the agent process's **launch environment** at startup, and the channel that reaches that launch env differs by surface (terminal `claude` vs Claude Desktop app). The `settings.json` `"env"` block does NOT control it - see [Setting the threshold (per surface)](#setting-the-threshold-per-surface) below before you set it, or it will silently do nothing.

**What you get:**
- Compaction triggers at ~50% of context instead of waiting until you're nearly full (configurable via env var)
- **After compaction Claude knows:** which TODOs are active, which agents are running in the background, which files were touched, which decisions were made
- State is saved to disk (`~/Desktop/claude/.claude/compact-state/`) with an archive of the last 20 compacts

## Tuning the threshold

`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` is the **percent of the auto-compaction window USED at which compaction fires** - lower = compacts earlier ([env-vars docs](https://code.claude.com/docs/en/env-vars)). It accepts an integer percentage. Common settings:

- `40` - aggressive, snapshots state more often (good if you run long sessions and want maximum recoverability)
- `50` - **recommended default**, balances frequency vs interruption
- `60-70` - relaxed, fewer compacts (use if you mostly run short sessions)
- Remove the env var entirely to fall back to Claude Code's built-in heuristic (~95%)

The value is read from the agent process's **launch environment** at startup, so changes require a Claude Code restart - AND the *channel* you set it through must actually reach that launch env. The `settings.json` `"env"` block does NOT (open bug [anthropics/claude-code#63186](https://github.com/anthropics/claude-code/issues/63186)): a value set there IS visible to subprocess tool calls (a Bash tool call can `echo $CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` and see it) but is NOT applied to the app's own auto-compact logic. The correct channel is **per surface** - see below.

> **1M-context (`[1m]`) model caveat** (verified-reported, unresolved as of agent 2.1.181 - issues [#53801](https://github.com/anthropics/claude-code/issues/53801) / [#53358](https://github.com/anthropics/claude-code/issues/53358)): on a `[1m]` model the percentage may be computed against a hardcoded ~200K internal window rather than the advertised 1M, so `50` can fire at ~50% of ~200K (~100K tokens), not 50% of 1M. If the firing point feels wrong on a `[1m]` model, either tune the number empirically or run routine sessions on the non-`[1m]` variant for predictable behavior.

## Setting the threshold (per surface)

`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` only takes effect if it lands in the agent's **launch** environment. Which mechanism does that depends on how you launch Claude Code. Pick your surface:

### Terminal / CLI `claude` (including headless `claude -p` from cron)

`export` it in your shell profile - the CLI inherits your shell's launch environment:

```bash
# ~/.zshrc  (or ~/.bashrc)
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50
```

Open a new shell (or `source` the profile) and start `claude`. On macOS, `launchctl setenv CLAUDE_AUTOCOMPACT_PCT_OVERRIDE 50` also works for this case. (The `settings.json` `"env"` block does NOT - #63186.)

### Claude Desktop app

Neither a shell `export` nor the `settings.json` `"env"` block reaches the Desktop-spawned agent. Per the [official docs](https://code.claude.com/docs/en/desktop.md):

> "The desktop app does not always inherit your full shell environment. On macOS, when you launch the app from the Dock or Finder, it reads your shell profile... to extract `PATH` and a fixed set of Claude Code variables, but other variables you export there are not picked up."

`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` is not in that fixed set, and `settings.json` env is ignored (#63186). The **only** channel that reaches the Desktop agent's launch env is the in-app **Local environment editor**:

1. In the prompt box, open the environment dropdown.
2. Hover **Local**, click the **gear icon**.
3. Add `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` = `50`.
4. Save, then **restart the session**.

(Stored encrypted on disk; applies to every local session.)

## Installation

### Automatic (part of install.sh)

If you run `bash install.sh`, the hooks are installed automatically (see step 8 in install.sh).

### Manual

**1. Copy hook scripts:**

```bash
mkdir -p ~/Desktop/claude/.claude/hooks
cp pupsik/hooks/pre-compact.sh ~/Desktop/claude/.claude/hooks/
cp pupsik/hooks/post-compact.sh ~/Desktop/claude/.claude/hooks/
chmod +x ~/Desktop/claude/.claude/hooks/*.sh
```

**2. Register in `~/.claude/settings.json`:**

Add to the `"hooks"` section (create it if missing). The recommended `"permissions"` block is also shown - `auto` is the default permission mode (auto-accepts safe operations, prompts on writes/shell).

> ⚠️ **The `"env"` block below does NOT set the auto-compact threshold.** `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` placed in `settings.json` env is visible to subprocess tool calls but is NOT applied to the app's own auto-compact logic (open bug [anthropics/claude-code#63186](https://github.com/anthropics/claude-code/issues/63186)). It's shown here only because the `"env"` block is the right home for OTHER variables you want subprocesses to see. To actually lower the threshold, follow [Setting the threshold (per surface)](#setting-the-threshold-per-surface) - shell `export` for the CLI, the in-app Local environment editor for Claude Desktop.

```json
{
  "permissions": {
    "defaultMode": "auto"
  },
  "env": {
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"
  },
  "hooks": {
    "PreCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/pre-compact.sh",
            "timeout": 10,
            "statusMessage": "Saving session state before auto-compact..."
          }
        ]
      },
      {
        "matcher": "manual",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/pre-compact.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PostCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/post-compact.sh",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "manual",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/post-compact.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Replace `<YOUR_HOME>` with your path (`/Users/<username>`). Example: `/Users/alice`.

Get it automatically:
```bash
echo "Your home: $HOME"
```

**3. Add `Compact Instructions` to `CLAUDE.md`:**

Add a section to `~/Desktop/claude/CLAUDE.md` (near the top, after Session Start Protocol):

```markdown
## Compact Instructions

On auto-compact, preserve in the summary:
- **Active TODOs** from TodoWrite (names + status)
- **Latest user question/request** in the current thread
- **Open loops:** agents still running in the background (agentId + what they're doing)
- **Key files modified this session** (full paths)
- **Decisions made this session** - one line each
- **Pending async ops** - email scans, scheduled tasks, background commands

DO NOT save: full tool output dumps, file contents (just give path + lines), intermediate research steps.

After compaction: the PostCompact hook will remind about `memory_search.py wake-up` and `compact-state/latest.json`. Run those FIRST, then continue the task.
```

**4. Restart Claude Code** (exit and re-enter the session).

## Verification

After installation and restart:

```bash
# Check hooks are executable
ls -la ~/Desktop/claude/.claude/hooks/

# Validate JSON
python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))"

# Test running a hook manually
echo '{"test": "payload"}' | ~/Desktop/claude/.claude/hooks/pre-compact.sh
```

Should print `=== PRE-COMPACT STATE SAVED ===` and create a file at `~/Desktop/claude/.claude/compact-state/latest.json`.

To verify the threshold env var loaded, watch for the status message `Saving session state before auto-compact...` when context hits ~50% (instead of ~95%). If it still fires only near the end:

1. Confirm you set the var through the channel that reaches the launch env for YOUR surface - shell `export` for the CLI, the in-app **Local environment editor** for Claude Desktop (see [Setting the threshold (per surface)](#setting-the-threshold-per-surface)). A value in the `settings.json` `"env"` block does NOT control the threshold ([#63186](https://github.com/anthropics/claude-code/issues/63186)), even though a `Bash` tool call will happily `echo` it.
2. Restart Claude Code - the value is read at session start, not mid-session.
3. On a `[1m]` model, the firing point may be miscomputed against a ~200K window ([#53801](https://github.com/anthropics/claude-code/issues/53801) / [#53358](https://github.com/anthropics/claude-code/issues/53358)) - see the caveat under [Tuning the threshold](#tuning-the-threshold).

On the next auto-compact, Claude should automatically run wake-up after recovery.

## Troubleshooting

- **Set the threshold but compaction still fires near the end (~95%):** you almost certainly set it in the `settings.json` `"env"` block, which does NOT apply to the app's auto-compact logic ([anthropics/claude-code#63186](https://github.com/anthropics/claude-code/issues/63186)). The env var must reach the agent's **launch** environment: shell `export` in `~/.zshrc`/`~/.bashrc` for the terminal CLI, or the in-app **Local environment editor** for Claude Desktop (Dock/Finder launches don't inherit your shell exports either, per the [desktop docs](https://code.claude.com/docs/en/desktop.md)). Full per-surface steps: [Setting the threshold (per surface)](#setting-the-threshold-per-surface). A quick gotcha: a `Bash` tool call can `echo $CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` and print `50` while the threshold is still the default - subprocess visibility ≠ applied to compaction. On a `[1m]` model also check the ~200K-window miscompute ([#53801](https://github.com/anthropics/claude-code/issues/53801) / [#53358](https://github.com/anthropics/claude-code/issues/53358)).
- **Hooks not triggering:** check `~/.claude/settings.json` is valid JSON. The path in `"command"` must be **absolute** (no `~/`).
- **Permission denied:** `chmod +x ~/Desktop/claude/.claude/hooks/*.sh`
- **Hook runs but Claude doesn't react:** verify the hook's stdout reaches the context. The hook writes to stdout - Claude will see it on the next turn.
- **Don't know what Claude saved:** check `~/Desktop/claude/.claude/compact-state/latest.json` and the archive in the same folder.

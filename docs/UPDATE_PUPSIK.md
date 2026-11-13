# Updating pupsik

Nothing updates behind your back. You run one command when you want the new version.

## By hand

From inside your clone:

```bash
bash tools/update.sh
```

It fetches `origin/main`, shows the new commits, refuses to run over uncommitted local edits (`--force` stashes and restores them), fast-forwards, then re-runs `install.sh --update-only`. Files you changed are never overwritten - the new version lands next to yours as `<file>.new`.

## By asking Claude

Install the optional skill once:

```bash
mkdir -p ~/.claude/skills/update-pupsik
cp templates/update-pupsik-skill.md.template ~/.claude/skills/update-pupsik/SKILL.md
```

Set `{{PUPSIK_CLONE}}` in that file to your clone path (install.sh also records it in `~/Desktop/claude/state/pupsik/clone-path.txt`). Then say "update pupsik" in any Claude Code session. Claude runs the same `git pull` + `tools/update.sh` and tells you what changed.

## Optional: weekly cron

```
# Every Monday at 09:00 local. Adjust the path to wherever you cloned.
0 9 * * 1 cd ~/code/pupsik && bash tools/update.sh >> ~/code/pupsik/.update.log 2>&1
```

## Did I edit a tool locally and forget to send it upstream?

```bash
bash tools/check-pupsik-upstream.sh
```

Read-only. For each tool pupsik installs, it says whether the clone and your workspace agree, and which side changed last.

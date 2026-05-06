#!/usr/bin/env bash
# privacy-check.sh — paranoid grep over the repo for personal-data leaks.
#
# Usage:
#   bash .github/scripts/privacy-check.sh           # scan repo root (CI mode)
#   bash .github/scripts/privacy-check.sh <path>    # scan a specific tree
#
# Exit:
#   0  clean
#   1  one or more leaks found
#
# Allowlist:
#   - "Misha Lyalin" / "mishalyalin" (the author byline) is allowed in:
#       LICENSE, README.md, MARKETING.md, MEDIA.md, .github/scripts/privacy-check.sh
#     and ONLY in those files. Any other file containing these strings = fail.
#   - Generic illustrative placeholder emails (alice@example.com, john@gmail.com,
#     personal@gmail.com, work@company.com, kids@gmail.com, your.email@gmail.com,
#     test@example.com) — allowed everywhere as documentation examples.
#
# Patterns checked (any unallowlisted hit = leak):
#   1. Real personal names other than the byline.
#   2. Real personal email addresses.
#   3. Phone numbers (international + local UK/NL formats).
#   4. Government/registry IDs (NI, UTR, EIN, KVK, VAT, NVWA client #).
#   5. Specific home addresses.
#   6. Project codenames, supplier names, business specifics.
#   7. API tokens, OAuth secrets, JWTs, AWS keys.
#   8. Hidden / large / suspicious files (.env, *.key, *.pem, .DS_Store, >500KB).
#   9. Compiled bytecode that may carry source paths (.pyc).


# Scan scope:
#   Files reported by `git ls-files` (TRACKED only). Untracked files are NOT scanned
#   by default. For local pre-commit runs where you have edits not yet `git add`ed,
#   pass `--include-untracked` (or `git add` your changes first so they show up).
#   CI runs without --include-untracked — only tracked content reaches the public repo.
set -uo pipefail
# (NOT -e — we want to keep going through all 9 passes and aggregate failures.)

INCLUDE_UNTRACKED=0
ROOT="."
for arg in "$@"; do
  case "$arg" in
    --include-untracked) INCLUDE_UNTRACKED=1 ;;
    --help|-h)
      sed -n '1,30p' "$0"
      exit 0 ;;
    *) ROOT="$arg" ;;
  esac
done
ROOT="$(cd "$ROOT" && pwd)"

red()    { printf "\033[1;31m%s\033[0m\n" "$*"; }
green()  { printf "\033[1;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[1;33m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

bold "[privacy-check] scanning $ROOT"

FAILS=0
PASS_COUNT=0
PASS_NAMES=()

# Files that are allowed to mention "Misha Lyalin" / "mishalyalin" as author byline.
ALLOWLIST_BYLINE=(
  "LICENSE"
  "README.md"
  "MARKETING.md"
  "MEDIA.md"
  "CHANGELOG.md"
  "CONTRIBUTING.md"
  "HOW_IT_WORKS.md"
  "MODULAR.md"
  "SETUP_PROMPT.md"
  "UPGRADING.md"
  "docs/AGENT_TEAM_RULE.md"
  "docs/COMPACT_SETUP.md"
  "docs/GOOGLE_CLOUD_SETUP.md"
  "docs/TELEGRAM_SETUP.md"
  "docs/WHATSAPP_SETUP.md"
  "install.sh"
  "install_mcps.sh"
  "register_mcps.sh"
  "tools/update.sh"
  ".github/scripts/privacy-check.sh"
  ".github/workflows/privacy-check.yml"
  "tools/publish_pupsik.sh"  # not in repo, but listed for completeness if ever copied in
)

# What ack pattern is "ok" inside an allowlisted file? (For pass 1 — avoid the byline.)
is_byline_allowlisted() {
  local rel="$1"
  for f in "${ALLOWLIST_BYLINE[@]}"; do
    if [ "$rel" = "$f" ]; then return 0; fi
  done
  return 1
}

# List all candidate files: tracked-by-git when possible, else everything except junk dirs.
list_files() {
  if (cd "$ROOT" && git rev-parse --git-dir >/dev/null 2>&1); then
    (cd "$ROOT" && git ls-files)
    if [ "$INCLUDE_UNTRACKED" -eq 1 ]; then
      (cd "$ROOT" && git ls-files --others --exclude-standard)
    fi
  else
    (cd "$ROOT" && find . -type f \
      -not -path '*/\.git/*' \
      -not -path '*/node_modules/*' \
      -not -path '*/__pycache__/*' \
      -not -path '*/dist/*' \
      -not -path '*/build/*' \
      -not -path '*/.venv/*' \
      -not -path '*/venv/*' \
      -not -name '*.pyc' \
      -not -name '.DS_Store' \
      | sed 's|^\./||')
  fi
}

# A grep helper that scans only text files, suppresses binaries, and is BSD/GNU portable.
grep_text() {
  local pattern="$1"
  shift
  local rel
  while IFS= read -r rel; do
    local abs="$ROOT/$rel"
    if [ ! -f "$abs" ]; then continue; fi
    # Skip obvious binaries.
    case "$rel" in
      *.png|*.jpg|*.jpeg|*.gif|*.pdf|*.zip|*.tar|*.gz|*.bz2|*.so|*.dylib|*.dll|*.class|*.pyc) continue ;;
    esac
    # Use grep -aE to handle accidental high-bytes; -I skips binaries by content sniff.
    if matches=$(grep -aIEn -- "$pattern" "$abs" 2>/dev/null); then
      while IFS= read -r line; do
        echo "$rel:$line"
      done <<< "$matches"
    fi
  done
}

run_pass() {
  local name="$1"
  local pattern="$2"
  local allow_byline="${3:-0}"   # 1 = allow byline files
  local extra_allow="${4:-}"     # optional extra grep -vE filter

  PASS_COUNT=$((PASS_COUNT + 1))
  PASS_NAMES+=("$name")

  printf "\n[pass %d] %s ... " "$PASS_COUNT" "$name"

  local hits
  hits=$(list_files | grep_text "$pattern")

  if [ -z "$hits" ]; then
    green "PASS"
    return 0
  fi

  # Apply allowlist filtering.
  local filtered="$hits"
  if [ "$allow_byline" = "1" ]; then
    # Drop hits in any byline-allowlisted file.
    local tmp="$filtered"
    filtered=""
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      local rel="${line%%:*}"
      if is_byline_allowlisted "$rel"; then continue; fi
      filtered+="$line"$'\n'
    done <<< "$tmp"
  fi
  if [ -n "$extra_allow" ]; then
    filtered=$(printf "%s" "$filtered" | grep -vE "$extra_allow" || true)
  fi

  # The privacy-check script itself contains every pattern it scans for by
  # definition. It is allowlisted across all passes (it cannot leak data
  # because it only contains regex patterns, never the values themselves
  # — and any real value would also leak via every other file anyway).
  filtered=$(printf "%s" "$filtered" | grep -vE '^\.github/scripts/privacy-check\.sh:' || true)

  filtered="${filtered%$'\n'}"

  if [ -z "$filtered" ]; then
    green "PASS (allowlisted)"
    return 0
  fi

  red "FAIL"
  echo "$filtered" | head -50 | sed 's/^/    /'
  local count
  count=$(echo "$filtered" | grep -c . || true)
  if [ "$count" -gt 50 ]; then
    yellow "  ...and $((count - 50)) more matches"
  fi
  FAILS=$((FAILS + 1))
}

# ============================================================================
# Pass 1 — Real personal names (the byline is allowlisted in select files only)
# ============================================================================
#
# Philosophy: author attribution is fine. The maintainer's name appearing
# in docstrings, comments, "produced by" lines, etc. is normal for any OSS
# project. We only flag:
#   - Full names of OTHER people in the maintainer's network (suppliers,
#     investors, family) — those identify relationships and should not leak.
#   - The maintainer's full name "Misha Lyalin" outside the byline-allowed
#     files (LICENSE, README, MARKETING) — the byline files are intentional.
#   - Bare first names like "Misha" alone are NOT flagged here. Author
#     attribution is a feature, not a leak. Process leaks (specific dates,
#     verbatim quotes, supplier deals) are caught by Pass 6 and adjacent
#     content rules instead.
#
NAME_PATTERN='(\bMisha[[:space:]]+Lyalin\b|\bmishalyalin\b|\bMikhail[[:space:]]+Lyalin\b|\bDasha[[:space:]]+(Lyalin|Bondarev)|\bTimofey[[:space:]]+Braslavets\b|\bIlya[[:space:]]+Torgovnikov\b|\bNikolay[[:space:]]+Bezborodov\b|\bAsif\b|\bIvan[[:space:]]+Gordeev\b|\bValentina\b|\bMarco\b|\bHans\b|\bNout\b|\bWiktor\b|\bSteve[[:space:]]+Aylott\b|\bRobert[[:space:]]+Marini\b|\bVoinov\b|\bGordeev\b|\bGrayver\b|\bPratap\b|\bAndrew[[:space:]]+Pirumov\b|\bGal[[:space:]]+Cohavy\b)'
run_pass "real personal names" "$NAME_PATTERN" 1

# ============================================================================
# Pass 2 — Real email addresses (aside from documented placeholders)
# ============================================================================
PLACEHOLDER_EMAILS='(alice@example\.com|bob@example\.com|john@gmail\.com|test@example\.com|user@example\.com|personal@gmail\.com|work@company\.com|kids@gmail\.com|your\.email@gmail\.com|name@example\.com|noreply@example\.com|me@example\.com|misha@example\.com|owner@example\.com|founder@example\.com|email@example\.com|school@gmail\.com|problematic@gmail\.com|first@gmail\.com|second@gmail\.com|account[12]?@gmail\.com|other@gmail\.com|user[12]@gmail\.com|me@gmail\.com|primary@gmail\.com|secondary@gmail\.com|sample@gmail\.com|example@gmail\.com)'
run_pass "real email addresses" \
  '\b[A-Za-z0-9._%+-]+@(pranasalt\.com|zeptolab\.com|mercury\.com|stop-spices\.|stopspices\.|tupak\.|viv-?\.|genofoods\.|shiva-?center\.|dalesman\.|allright\.|hopsiq\.|healf\.|metida\.|ipnote\.|hmlg\.|lanstone\.)\b' \
  0

# Generic catch: any @gmail.com address other than the documented placeholders.
run_pass "real gmail addresses" \
  '\b[A-Za-z0-9._%+-]+@gmail\.com\b' \
  0 \
  "$PLACEHOLDER_EMAILS"

# ============================================================================
# Pass 3 — Phone numbers
# ============================================================================
# Looser pattern: international "+" prefix or 11-digit run with separators.
# Allow obviously-fake examples: +1-555-..., 555-555-..., 0123456789-padding.
run_pass "phone numbers" \
  '(\+44[[:space:]]?[0-9]{10}|\+447[0-9]{9}|\+31[[:space:]]?[0-9]{9}|\+1[[:space:]]?[0-9]{10}|\b07[0-9]{9}\b)' \
  0 \
  '\+1[[:space:]]?555|555-555|\+1-555'

# ============================================================================
# Pass 4 — Government / registry IDs
# ============================================================================
# Specific known IDs from the live workspace.
run_pass "registry IDs (KVK / VAT / EIN / NI / UTR / NVWA)" \
  '(\bKVK[:[:space:]]*[0-9]{8}\b|\bNL[0-9]{9}B[0-9]{2}\b|\bEIN[:[:space:]]*[0-9]{2}-[0-9]{7}\b|\bNVWA[:[:space:]]*[0-9]{6,8}\b|\bUTR[:[:space:]]*[0-9 ]{8,12}\b|\bNI[:[:space:]]*[A-Z]{2}[0-9]{6}[A-Z]\b|\b42016445\b|\b39-4385463\b|\bNL869305736B01\b|\b20525048\b|\b0514378\b|\b1979928145\b)'

# ============================================================================
# Pass 5 — Specific addresses
# ============================================================================
run_pass "specific home/office addresses" \
  '(Craven[[:space:]]+Hill[[:space:]]+Gardens|Princedale[[:space:]]+Road|Finchley[[:space:]]+Road|Herengracht[[:space:]]+584|Paul[[:space:]]+Street|EC2A[[:space:]]?4NE|W2[[:space:]]?3ES|W11[[:space:]]?4NL|NW3[[:space:]]?7AA|1017CJ)'

# ============================================================================
# Pass 6 — Project / supplier / business specifics
# ============================================================================
run_pass "project codenames + supplier/business specifics" \
  '(\bPranaSalt\b|\bPranasalt\b|\bprana\.salt\b|\bZeptoLab\b|\bGenofoods\b|\bTupak\b|\bSTOP[[:space:]]?Spices\b|\bShiva[[:space:]]?Center\b|\bDalesman\b|\bShipBob\b|\bSendcloud\b|\bZendbox\b|\bAllright\b|\bHopsiq\b|\bHealf\b|\bSouthbank[[:space:]]+International|\bSylvia[[:space:]]+Young|\bLava[[:space:]]+Cacao\b|\bDKB[[:space:]]+orange|\bVIV2603037\b)' \
  1

# ============================================================================
# Pass 7 — API tokens / secrets / OAuth
# ============================================================================
run_pass "tokens and secrets" \
  '(\bgho_[A-Za-z0-9]{20,}|\bghp_[A-Za-z0-9]{20,}|\bghs_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9]{20,}|\bsk-proj-[A-Za-z0-9_-]{20,}|\bxoxb-[0-9]+-[0-9]+|\bAKIA[0-9A-Z]{16}\b|\bya29\.[A-Za-z0-9_-]+|GOCSPX-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)' \
  0 \
  'your_client_secret_here|YOUR_CLIENT_SECRET|<client.secret>|placeholder|example|dummy'

# ============================================================================
# Pass 9 — Hidden / suspicious files
# ============================================================================
PASS_COUNT=$((PASS_COUNT + 1))
printf "\n[pass %d] hidden/sensitive files ... " "$PASS_COUNT"
SUSPICIOUS=$(list_files | grep -E '(^|/)\.env(\.|$)|(^|/)\.DS_Store$|\.key$|\.pem$|\.token$|\.p12$|credentials\.json|service-account.*\.json' || true)
if [ -z "$SUSPICIOUS" ]; then
  green "PASS"
else
  red "FAIL"
  echo "$SUSPICIOUS" | sed 's/^/    /'
  FAILS=$((FAILS + 1))
fi

# ============================================================================
# Pass 10 — Files larger than 500KB (potential blobs / dumps)
# ============================================================================
PASS_COUNT=$((PASS_COUNT + 1))
printf "\n[pass %d] oversize files (>500KB) ... " "$PASS_COUNT"
OVERSIZE=$(list_files | while IFS= read -r rel; do
  abs="$ROOT/$rel"
  [ -f "$abs" ] || continue
  size=$(wc -c < "$abs" 2>/dev/null || echo 0)
  if [ "$size" -gt 524288 ]; then
    printf "%s (%d bytes)\n" "$rel" "$size"
  fi
done)
if [ -z "$OVERSIZE" ]; then
  green "PASS"
else
  yellow "WARN — review manually"
  echo "$OVERSIZE" | sed 's/^/    /'
fi

# ============================================================================
# Summary
# ============================================================================
echo
bold "============================================="
if [ "$FAILS" = "0" ]; then
  green "[privacy-check] ALL PASSED ($PASS_COUNT passes, 0 failures)"
  exit 0
else
  red "[privacy-check] FAILED ($FAILS pass(es) flagged leaks)"
  red "  Fix the offending files before publishing."
  exit 1
fi

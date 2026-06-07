#!/bin/bash
# monitor-commit-freshness.sh — alert if RiveryIO/complexity-analyzer's GitHub
# `main` branch has not received a commit within MAX_AGE_HOURS.
#
# WHY THE REMOTE, NOT LOCAL: the daily sync (com.user.complexity-sync) keeps
# committing locally even when its `git push` is broken, so the local repo
# always looks "fresh". Only the *remote* tip reveals a dead push. This is
# exactly the failure that hid for 7 days in June 2026 (the gh token in
# ~/.config/gh-token expired and every scheduled push silently 403'd).
#
# Exit codes: 0 = fresh, 1 = stale (alerted), 2 = could not verify (alerted).
set -u

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# Same CA bundle the sync job uses (corporate TLS interception). git needs
# GIT_SSL_CAINFO; without it https to github fails under launchd.
CA_BUNDLE="/Users/ohadperry/.ssl/combined_certs.pem"
[ -r "$CA_BUNDLE" ] && export GIT_SSL_CAINFO="$CA_BUNDLE"

REPO_DIR="/Users/ohadperry/Documents/Dev/complexity-analyzer"
REMOTE_HOST_PATH="github.com/RiveryIO/complexity-analyzer.git"
BRANCH="main"
TOKEN_FILE="$HOME/.config/gh-token"
# Library/Logs is NOT TCC-protected like ~/Documents, so launchd appends here
# reliably (the sync job's ~/Documents log intermittently hits EINTR).
LOG_FILE="$HOME/Library/Logs/complexity-monitor.log"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-36}"
NOTIFIER="/opt/homebrew/bin/terminal-notifier"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S'): $*" >> "$LOG_FILE"; }

notify() { # $1 = subtitle, $2 = message
  [ -x "$NOTIFIER" ] && "$NOTIFIER" \
    -title "⚠️ complexity-analyzer not pushing" \
    -subtitle "$1" \
    -message "$2" \
    -group "complexity-monitor" \
    -sound default >/dev/null 2>&1
}

cd "$REPO_DIR" 2>/dev/null || { log "FATAL: cannot cd to $REPO_DIR"; notify "Monitor error" "Cannot access $REPO_DIR"; exit 2; }

# Authenticated URL — the osxkeychain helper is unavailable under launchd, so we
# use the same token file the sync job pushes with.
if [ -r "$TOKEN_FILE" ]; then
  TOKEN=$(tr -d '\n\r' < "$TOKEN_FILE")
  REMOTE_URL="https://x-access-token:${TOKEN}@${REMOTE_HOST_PATH}"
else
  REMOTE_URL="https://${REMOTE_HOST_PATH}"
fi

# Remote tip SHA, without mutating any local ref.
REMOTE_SHA=$(/usr/bin/git ls-remote "$REMOTE_URL" "refs/heads/$BRANCH" 2>>"$LOG_FILE" | cut -f1)
if [ -z "$REMOTE_SHA" ]; then
  log "UNVERIFIED: ls-remote returned nothing (expired token or no network?)"
  notify "Cannot verify remote" "ls-remote failed — token expired or offline?"
  exit 2
fi

# The remote tip is normally already an ancestor of local main, so read its date
# locally without fetching; otherwise fetch just that branch into FETCH_HEAD.
COMMIT_EPOCH=$(/usr/bin/git log -1 --format=%ct "$REMOTE_SHA" 2>/dev/null)
if [ -z "$COMMIT_EPOCH" ]; then
  /usr/bin/git fetch --quiet "$REMOTE_URL" "$BRANCH" 2>>"$LOG_FILE" \
    && COMMIT_EPOCH=$(/usr/bin/git log -1 --format=%ct FETCH_HEAD 2>/dev/null)
fi
if [ -z "$COMMIT_EPOCH" ]; then
  log "UNVERIFIED: resolved remote tip $REMOTE_SHA but could not read its commit date"
  notify "Cannot verify remote" "Got SHA ${REMOTE_SHA:0:7} but no commit date"
  exit 2
fi

NOW=$(date +%s)
AGE_HOURS=$(( (NOW - COMMIT_EPOCH) / 3600 ))
SHORT_SHA=${REMOTE_SHA:0:7}
COMMIT_WHEN=$(date -r "$COMMIT_EPOCH" '+%Y-%m-%d %H:%M')

if [ "$AGE_HOURS" -gt "$MAX_AGE_HOURS" ]; then
  log "STALE: GitHub $BRANCH tip $SHORT_SHA is ${AGE_HOURS}h old (> ${MAX_AGE_HOURS}h), last commit $COMMIT_WHEN"
  notify "No push for ${AGE_HOURS}h" "GitHub $BRANCH @ $SHORT_SHA, last commit $COMMIT_WHEN"
  exit 1
fi

log "OK: GitHub $BRANCH tip $SHORT_SHA is ${AGE_HOURS}h old (<= ${MAX_AGE_HOURS}h), last commit $COMMIT_WHEN"
exit 0

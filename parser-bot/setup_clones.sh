#!/usr/bin/env bash
# One-time: bot-owned shared clones (git worktrees cannot build: parent pom copies .git/HEAD as a resource).
set -euo pipefail
ROOT=/Users/trungthach/IdeaProjects
BOT=$ROOT/worktrees/bot
mkdir -p "$BOT"
[ -d "$BOT/moso-pricing" ] || git clone --shared -b master "$ROOT/moso-pricing" "$BOT/moso-pricing"
[ -d "$BOT/packs" ]        || git clone --shared -b master "$ROOT/packs" "$BOT/packs"
for r in moso-pricing packs; do
  git -C "$BOT/$r" remote set-url origin "$(git -C "$ROOT/$r" remote get-url origin)"
  git -C "$BOT/$r" fetch -q origin && git -C "$BOT/$r" checkout -q master && git -C "$BOT/$r" reset -q --hard origin/master
done
echo "bot clones ready under $BOT"

#!/usr/bin/env bash
set -euo pipefail
BOT=/Users/trungthach/IdeaProjects/worktrees/bot
for r in moso-pricing packs; do git -C "$BOT/$r" checkout -q master && git -C "$BOT/$r" pull -q --ff-only; done
(cd "$BOT/moso-pricing" && mvn -q install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true)
echo "clones on master, moso-pricing installed to ~/.m2"

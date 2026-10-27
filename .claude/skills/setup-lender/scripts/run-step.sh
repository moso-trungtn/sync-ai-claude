#!/bin/zsh
# usage: run-step.sh <step method> <LenderType> [server app id, empty = local] [extra -D...]
# e.g.   run-step.sh step6LoadAdjustments SpringEQ "" -Dadj.parser=<FQCN> -Dratesheet=<RatesheetFiles constant>
set -u
STEP=$1; LENDER=$2; SERVER=${3:-}; shift 3 2>/dev/null || shift $#
LOG_DIR=${SETUP_LENDER_LOG_DIR:-/tmp}
LOG=$LOG_DIR/setup-lender-$LENDER-$STEP.log
cd ~/IdeaProjects/moso
mvn -o ${SETUP_LENDER_GOAL:-test} -Dgwt.compiler.skip=true -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest="SetupLenderTools#$STEP" -Dlender="$LENDER" -Dserver="$SERVER" \
  -Dmaven.test.additionalClasspath="$HOME/IdeaProjects/packs/loan/target/test-classes" \
  -Djunit.jupiter.conditions.deactivate='*' "$@" > "$LOG" 2>&1
RC=$?
echo "exit $RC  log: $LOG"
grep -E "Connected to|Uploading to NS|Parsed |Tests run:|Caused by|No space left" "$LOG" | grep -v "^\[ERROR\] *$" | head -15
exit $RC

#!/bin/bash
# The monitor's /config 「Nav2」 tab (REV-132, DEC-209, IFD-54, TS-45) on the VM test stack: the recovery count saved in the monitor
# is used by Nav2 from the next start of the stack (the same launch as gouda.sh start), and refused outside 1..PRM-18.
#   N1 first start: nothing saved -> the BT has PRM-18, run/nav2/recovery.json says so
#   N2 save 0 (refused) and 3 (accepted); the running Nav2 keeps PRM-18, the next start will use 3
#   N3 restart: the BT has 3, the monitor shows 3 in use
set -o pipefail
WS=${WS:-~/gouda_rev128_ws}; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/nav2rec
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-78}
rm -rf $ROOT; mkdir -p $ROOT
stack() { bash $REPO/gouda_core/test/stack.sh $1 $ROOT; }
trap 'stack stop' EXIT
bt() { grep -o 'NavigateRecovery"[^>]*number_of_retries="[0-9]*"\|number_of_retries="[0-9]*"[^>]*name="NavigateRecovery"' $ROOT/run/nav2/navigate_through_poses.xml | grep -o 'number_of_retries="[0-9]*"'; }
api() { curl -s "$(cat $ROOT/run/monitor.url)/api/nav2_recovery" | python3 -c "
import json,sys; c=json.load(sys.stdin); n=c.get('next_start') or {}; u=c.get('in_use') or {}
print('  saved', c['values'], 'limits', c.get('limits'), '| next start', n.get('value'), n.get('source'), '| in use', u.get('value'), u.get('source'))"; }
save() { curl -s -X POST -H 'Content-Type: application/json' -d "{\"recovery_number_of_retries\": \"$1\"}" "$(cat $ROOT/run/monitor.url)/api/nav2_recovery" | python3 -c "import json,sys; j=json.load(sys.stdin); print('  save $1: ok=%s %s' % (j['ok'], j['message']))"; }
echo "=== N1 first start"
stack start || exit 1; sleep 3
echo "  BT: $(bt)"; echo "  recovery.json: $(cat $ROOT/run/nav2/recovery.json | tr -d '\n')"; api
echo "=== N2 save"
save 0; save 3; api; echo "  BT of the running Nav2: $(bt)"
echo "=== N3 restart"
stack stop; stack start || exit 1; sleep 3
echo "  BT: $(bt)"; echo "  recovery.json: $(cat $ROOT/run/nav2/recovery.json | tr -d '\n')"; api
grep -E "gouda_nav2.*recovery count" $ROOT/run/stack.launch.log | cut -c1-200

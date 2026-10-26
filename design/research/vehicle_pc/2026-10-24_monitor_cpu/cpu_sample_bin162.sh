#!/bin/bash
# Read-only (第162便): CPU % per process over $1 seconds from /proc (utime+stime), by process name; no command lines are read.
secs=${1:-60}
snap() { for d in /proc/[0-9]*; do [ -r $d/stat ] || continue; s=$(cat $d/stat 2>/dev/null) || continue; n=${s#*(}; n=${n%%)*}; r=${s##*) }; set -- $r; echo "${d#/proc/} $n $(( ${12} + ${13} ))"; done; }
snap > /tmp/cpu_a.$$; t0=$(date +%s.%N); sleep $secs; snap > /tmp/cpu_b.$$; t1=$(date +%s.%N)
awk -v dt=$(echo "$t1 - $t0" | bc) 'NR==FNR{a[$1]=$3; n[$1]=$2; next} ($1 in a){d=$3-a[$1]; c[$2]+=d} END{for(k in c) if (c[k]/dt>=1) printf "%6.1f%% %s\n", c[k]/dt, k}' /tmp/cpu_a.$$ /tmp/cpu_b.$$ | sort -rn | head -15
echo "loadavg: $(cat /proc/loadavg)"; rm -f /tmp/cpu_a.$$ /tmp/cpu_b.$$

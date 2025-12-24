#!/bin/bash
# ChronosPulse Real-Time Monitor
# Author: subhanigori@gmail.com

watch -n 2 -c "
echo -e 'ChronosPulse Sync Dashboard | $(date)'
echo -e '------------------------------------------------------------'
echo -e 'SYSTEM TRACKING:'
chronyc tracking | grep -E 'Reference ID|Stratum|Last offset|RMS offset|Frequency'
echo -e '\nPEER SELECTION (Wait for *):'
echo -e 'M S Name/IP Address         Stratum Poll Reach LastRx Last sample'
chronyc -n sources | grep -E '^\^\*' --color=always || chronyc -n sources
echo -e '------------------------------------------------------------'
echo -e 'Legend: * = Active Sync, + = Combined, ? = Unreachable/Pending'
"

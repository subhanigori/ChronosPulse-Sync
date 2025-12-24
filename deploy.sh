#!/bin/bash
# ChronosPulse v1.3.3 - Debug Edition
# Author: subhanigori@gmail.com

SENSITIVITY_THRESHOLD=0.15
OPTIMIZER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="/etc/chrony.conf"

if [ "$EUID" -ne 0 ]; then echo "Run as root"; exit 1; fi
cd "$OPTIMIZER_DIR"

# 1. Run Python Analysis
python3 optimizer.py

# 2. Extract and Validate Data
if [ -f .best_ntp ]; then
    # Clean the input to remove any weird whitespace
    RAW_DATA=$(tr -d '\r' < .best_ntp | xargs)
    echo "[DEBUG] Raw Data Received: $RAW_DATA"

    # Use a safer way to parse the comma-separated values
    NEW_SVR=$(echo "$RAW_DATA" | cut -d',' -f1)
    NEW_LAT=$(echo "$RAW_DATA" | cut -d',' -f2)
    NTS_FLAG=$(echo "$RAW_DATA" | cut -d',' -f3)
    RTC_STATUS=$(echo "$RAW_DATA" | cut -d',' -f4)

    if [ -z "$NEW_SVR" ] || [ -z "$NEW_LAT" ]; then
        echo "[ERROR] Parser failed to extract fields. Data: $RAW_DATA"
        exit 1
    fi

    # 3. Hardware Drift Alert
    if [ "$RTC_STATUS" == "HW_DEGRADED" ]; then
        logger -p auth.crit "ChronosPulse: High Hardware Drift on $(hostname)"
        echo "!!! HW WARNING: Drift detected !!!"
    fi

    # 4. Performance Math
    CURRENT_SVR=$(grep "^server" "$CONF" | grep -v "#" | head -1 | awk '{print $2}')
    if [ -n "$CURRENT_SVR" ]; then
        CURRENT_LAT=$(ntpdate -q "$CURRENT_SVR" 2>/dev/null | grep "delay" | awk '{print $6}' | tr -d ',')
    fi
    [ -z "$CURRENT_LAT" ] && CURRENT_LAT=999.0

    # Ensure NEW_LAT is a valid float for Python math
    IMPROVEMENT=$(python3 -c "print(($CURRENT_LAT - $NEW_LAT) / $CURRENT_LAT if $CURRENT_LAT != 0 else 1.0)")

    echo "[INFO] Current: $CURRENT_LAT | New: $NEW_LAT | Gain: $IMPROVEMENT"

    if (( $(echo "$IMPROVEMENT > $SENSITIVITY_THRESHOLD" | bc -l) )); then
        echo "[ACTION] Optimizing config for $NEW_SVR..."
        
        NTS_OPT=""; [[ "$NTS_FLAG" == "nts" ]] && NTS_OPT="nts"

        # Update Config
        sed -i '/^server/d' "$CONF"
        echo "server $NEW_SVR iburst $NTS_OPT" >> "$CONF"
        systemctl restart chronyd
        
        echo "[VERIFY] Waiting 60s for Stratum stabilization..."
        sleep 60
        STRATUM=$(chronyc -n sources | grep "^\^\*" | awk '{print $3}')
        echo "[SUCCESS] Verified Stratum: ${STRATUM:-Unknown}"
    else
        echo "[SKIP] Improvement below threshold."
    fi
else
    echo "[ERROR] .best_ntp file missing."
fi

# ChronosPulse NTP Optimizer v1.3.4

**Architect:** [subhanigori@gmail.com](mailto:subhanigori@gmail.com)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)

**ChronosPulse** is an enterprise-grade NTP lifecycle manager. It transforms standard time synchronization into a self-healing, high-precision telemetry engine. Designed for RHEL 10, Ubuntu 25, and high-frequency trading or database environments where every millisecond counts.

## 🚀 Architecture Overview

ChronosPulse uses a decoupled architecture where the **Analytics Engine** (Python) performs heavy telemetry and the **Orchestrator** (Bash) manages system-level configurations.


## Project Summary
ChronosPulse is an enterprise-grade NTP management suite designed for high-availability Linux environments (RHEL 10, Ubuntu 25+). It automates the selection of high-precision time sources, enforces Network Time Security (NTS), and performs deep hardware diagnostics to ensure system clock integrity.

## Why ChronosPulse?
In distributed enterprise systems, clock drift leads to data corruption and authentication failures. Standard NTP clients often rely on static pools with high jitter. ChronosPulse dynamically "scouts" the lowest-latency peers and verifies their authority (Stratum 1/2) before committing changes to the system.

✨ Key Features
- **Dynamic Telemetry:** Scrapes and analyzes performance of global public time servers.
- **NTS Integration:** Automatically enables Network Time Security (NTS) for encrypted time sync.
- **Hardware Integrity Guard:** Detects failing CMOS batteries or oscillators by monitoring Drift PPM.
- **Sensitivity Gating:** Implements a 15% performance threshold to avoid unnecessary service restarts.
- **Post-Update Verification:** Ensures the system reaches a Stratum 1 or 2 state within 60 seconds of reconfiguration.
- **Security (NTS): Automatically detects and enforces Network Time Security for encrypted handshakes.
- **Hardware Diagnostic: Monitors the RTC (Real-Time Clock) for frequency drift (>200ppm) to detect failing CMOS batteries.
- **Sync-Aware Slew: Prevents aggressive "clock jumps" by validating drift before applying changes.
- **Real-Time Dashboard: Built-in monitoring tool for tracking convergence.

🛠️ Installation & Usage
1. Requirements
Ensure chrony and ntpdate are installed:

2. Deployment
Manual Linux Bash Run

# Ubuntu/Debian
sudo apt install chrony ntpdate python3-requests

# RHEL/AlmaLinux
sudo dnf install chrony ntpdate python3-requests

Git Deployment:

git clone [https://github.com/yourusername/ChronosPulse.git](https://github.com/yourusername/ChronosPulse.git)
cd ChronosPulse
chmod +x *.sh *.py
sudo ./deploy.sh

3. Monitoring
Launch the dashboard to see the clock stabilize in real-time:

./dashboard.sh


📊 Technical Case Study
During testing in a high-latency network environment, ChronosPulse successfully identified a Stratum 1 source that reduced system time offset from 999ms (unmanaged) to < 50ms, while simultaneously flagging a hardware drift of 12.5ppm, well within healthy operational parameters.

## Installation & Usage
1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/chronospulse-ntp-optimizer.git](https://github.com/subhanigori/chronospulse-ntp-optimizer.git)
   cd chronospulse-ntp-optimizer


```mermaid
graph TD
    A[Cron Job / Manual Start] --> B[deploy.sh Orchestrator]
    B --> C[optimizer.py Analytics Engine]
    
    subgraph "Analytics Phase"
    C --> C1[Scrape Public NTP Sources]
    C --> C2[UDP 123 Latency Tests]
    C2 --> C3[Identify Best Stratum 1/2 Peer]
    C --> C4[Analyze RTC Drift PPM]
    end

    C3 & C4 --> D[.best_ntp State File]
    D --> E{Sensitivity Gate}
    
    E -- Gain < 15% --> F[Log & Exit: No Change]
    E -- Gain > 15% --> G[Update /etc/chrony.conf]
    
    G --> H[Restart chronyd Service]
    H --> I[Post-Update Verification: 60s]
    I --> J[Verify Stratum Authority]

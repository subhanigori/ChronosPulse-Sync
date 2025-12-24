# ChronosPulse NTP Optimizer v1.3.0

**Architect:** [subhanigori@gmail.com](mailto:subhanigori@gmail.com)

## Project Summary
ChronosPulse is an enterprise-grade NTP management suite designed for high-availability Linux environments (RHEL 10, Ubuntu 25+). It automates the selection of high-precision time sources, enforces Network Time Security (NTS), and performs deep hardware diagnostics to ensure system clock integrity.

## Why ChronosPulse?
In distributed enterprise systems, clock drift leads to data corruption and authentication failures. Standard NTP clients often rely on static pools with high jitter. ChronosPulse dynamically "scouts" the lowest-latency peers and verifies their authority (Stratum 1/2) before committing changes to the system.

## Key Features
- **Dynamic Telemetry:** Scrapes and analyzes performance of global public time servers.
- **NTS Integration:** Automatically enables Network Time Security (NTS) for encrypted time sync.
- **Hardware Integrity Guard:** Detects failing CMOS batteries or oscillators by monitoring Drift PPM.
- **Sensitivity Gating:** Implements a 15% performance threshold to avoid unnecessary service restarts.
- **Post-Update Verification:** Ensures the system reaches a Stratum 1 or 2 state within 60 seconds of reconfiguration.

## Installation & Usage
1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/chronospulse-ntp-optimizer.git](https://github.com/subhanigori/chronospulse-ntp-optimizer.git)
   cd chronospulse-ntp-optimizer


<img width="902" height="636" alt="image" src="https://github.com/user-attachments/assets/022c88dd-c5f7-4ae0-b8e6-0645345570a0" />

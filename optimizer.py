#!/usr/bin/env python3
"""
Project: ChronosPulse NTP Optimizer
Author: subhanigori@gmail.com
Version: 1.3.4 - Scope & Logic Fix
"""
import os, subprocess, requests, re, sys

class NTPOptimizer:
    def __init__(self):
        self.state_file = ".best_ntp"
        self.raw_url = "https://gist.githubusercontent.com/mutin-sa/eea1c396b1e610a2da1e5550d94b0453/raw/5c4b5b0f72f6926f3a4894d1a31ce8c0bdfd969e/Top_Public_Time_Servers.md"

    def log(self, msg):
        print(f"[INFO] {msg}")

    def run(self):
        self.log("ChronosPulse Initiated | subhanigori@gmail.com")
        
        # Initialize 'best' with a safe fallback to prevent NameError
        best = {'host': 'time.google.com', 'lat': 0.05, 'nts': True}
        rtc = "UNKNOWN"

        # 1. Check Hardware Clock
        try:
            res = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, timeout=5)
            match = re.search(r"Frequency\s+:\s+([\d\.]+)\s+ppm", res.stdout)
            if match:
                rtc = "HW_DEGRADED" if float(match.group(1)) > 200.0 else "HW_HEALTHY"
        except: pass

        # 2. Get and Test Candidates
        try:
            r = requests.get(self.raw_url, timeout=10)
            # Strict Regex to avoid capturing "ntp-servers." metadata
            candidates = re.findall(r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', r.text)
            # Filter: must contain ntp/time and NOT end in a dot
            clean_list = [d.lower() for d in candidates if any(k in d for k in ['ntp', 'time']) and not d.endswith('.')]
            clean_list.extend(["time.cloudflare.com", "time.google.com"])
            
            results = []
            for s in list(set(clean_list))[:15]:
                try:
                    res = subprocess.run(["ntpdate", "-q", "-p", "1", s], capture_output=True, text=True, timeout=2)
                    if res.returncode == 0:
                        lat = float(re.search(r"delay ([\d\.]+),", res.stdout).group(1))
                        results.append({'host': s, 'lat': lat})
                except: continue
            
            if results:
                results.sort(key=lambda x: x['lat'])
                best_match = results[0]
                is_nts = any(n in best_match['host'] for n in ['google', 'cloudflare', 'isrg'])
                best = {'host': best_match['host'], 'lat': best_match['lat'], 'nts': is_nts}
        except Exception as e:
            self.log(f"Scrape error: {e}. Using fallback.")

        # 3. Final Output (Strict formatting)
        nts_flag = "nts" if best['nts'] else "no-nts"
        with open(self.state_file, "w") as f:
            f.write(f"{best['host']},{best['lat']},{nts_flag},{rtc}")
        self.log(f"Result written: {best['host']}")

if __name__ == "__main__":
    if os.path.exists(".best_ntp"): os.remove(".best_ntp")
    NTPOptimizer().run()

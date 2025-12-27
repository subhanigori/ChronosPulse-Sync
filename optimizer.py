#!/usr/bin/env python3
"""
NTP Server Optimizer - Enterprise Edition
Automatic NTP server selection and optimization for Linux client systems

Author: subhanigori@gmail.com
Version: 2.0.0
License: MIT
Copyright (c) 2024 subhanigori@gmail.com

This tool automatically discovers, tests, and configures the optimal NTP server
for Linux systems based on comprehensive performance metrics with focus on
reliability and accuracy. Designed for client servers requiring optimal time sync.
"""

import os
import sys
import time
import json
import logging
import argparse
import subprocess
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import statistics

# ============================================================================
# AUTHOR INFORMATION & VERSION
# Developer: subhanigori@gmail.com
# ============================================================================
__author__ = "subhanigori@gmail.com"
__version__ = "2.0.0"
__copyright__ = "Copyright (c) 2024 subhanigori@gmail.com"

# ============================================================================
# CONFIGURATION SECTION
# All user-configurable settings are here for easy modification
# Developer: subhanigori@gmail.com
# ============================================================================

CONFIG = {
    # Testing Configuration
    'testing': {
        'samples_per_server': 3,          # Number of test samples per server
        'timeout': 5,                      # Timeout for each query (seconds)
        'interval_hours': 6,               # How often to run optimization (hours)
        'max_servers_to_test': 20,        # Maximum servers to test per run
    },
    
    # Server Selection Criteria (Tuned for Reliability & Accuracy)
    # Developer: subhanigori@gmail.com - Optimized for client server use
    'selection': {
        'min_stratum': 1,                  # Minimum stratum level (1 = atomic clock)
        'max_stratum': 3,                  # Maximum stratum level (tighter control)
        
        # Weights (sum = 1.0) - Prioritizing reliability and accuracy
        'weight_jitter': 0.35,             # Stability (high priority for reliability)
        'weight_reachability': 0.30,       # Reliability (high priority)
        'weight_stratum': 0.25,            # Accuracy (high priority)
        'weight_latency': 0.10,            # Speed (lower priority for client use)
        
        'min_score': 60.0,                 # Minimum acceptable score (0-100)
        'stability_threshold': 2,          # Require N consecutive better scores before switch
        'hysteresis_percent': 15,          # Don't switch if current is within N% of best
    },
    
    # Logging Configuration
    'logging': {
        'level': 'INFO',                   # DEBUG, INFO, WARNING, ERROR
        'retention_days': 30,              # Days to keep historical data
    },
    
    # Server Sources (tried in order with fallbacks)
    'server_sources': [
        'https://gist.githubusercontent.com/mutin-sa/eea1c396b1e610a2da1e5550d94b0453/raw/top_public_time_servers.md',
        'https://www.ntppool.org/zone/@',  # Will be replaced with region
    ],
    
    # Geographic Preference (auto-detected from system timezone)
    'geographic': {
        'auto_detect': True,               # Automatically detect region from locale
        'prefer_regional': True,           # Prefer servers in same region
        'fallback_to_global': True,       # Use global servers if regional unavailable
    },
    
    # Email Notification Settings
    # Developer: subhanigori@gmail.com
    'notifications': {
        'email': {
            'enabled': False,              # Set to True to enable email alerts
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'use_tls': True,
            'from_address': 'ntp-optimizer@example.com',
            'to_addresses': ['admin@example.com'],  # List of recipients
            'username': '',                # SMTP username
            'password': '',                # SMTP password or app password
            'send_on_change': True,       # Send email when server changes
            'send_on_error': True,        # Send email on errors
        }
    },
    
    # Advanced Settings
    'advanced': {
        'blacklist_after_failures': 3,     # Blacklist server after N failures
        'whitelist': [],                   # Restrict to these servers only (empty = allow all)
        'test_current_first': True,       # Test current server before others
        'backup_configs': True,            # Keep backup of configurations
        'max_backups': 5,                  # Maximum number of backups to keep
    }
}


@dataclass
class NTPServer:
    """
    Data class for NTP server information
    Developer: subhanigori@gmail.com
    """
    hostname: str
    offset: float = 999.0          # milliseconds
    jitter: float = 999.0          # milliseconds
    stratum: int = 16
    reachability: float = 0.0      # percentage
    score: float = 0.0
    tested: bool = False
    region: str = ""               # Geographic region
    
    def to_dict(self):
        return asdict(self)


class NTPOptimizer:
    """
    Main NTP Optimizer class for client server optimization
    
    Focuses on reliability and accuracy over raw speed.
    Handles NTP service detection, server testing, and configuration management.
    
    Developer: subhanigori@gmail.com
    """
    
    def __init__(self, config: dict = None, dry_run: bool = False):
        """
        Initialize NTP Optimizer
        
        Args:
            config: Configuration dictionary (uses default if None)
            dry_run: If True, don't make actual changes
            
        Developer: subhanigori@gmail.com
        """
        self.dry_run = dry_run
        self.config = config if config else CONFIG
        self.script_dir = Path(__file__).parent.absolute()
        self.log_dir = self.script_dir / "logs"
        self.data_dir = self.script_dir / "data"
        
        # Create directories
        self.log_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # NTP service info
        self.ntp_service = None
        self.ntp_config_file = None
        
        # Geographic info
        self.detected_region = None
        self.detected_continent = None
        
        # Blacklist tracking
        self.blacklist = set()
        self._load_blacklist()
        
        # Print banner
        self.logger.info(f"{'='*80}")
        self.logger.info(f"NTP Server Optimizer v{__version__} - Enterprise Edition")
        self.logger.info(f"Optimized for Client Server Reliability & Accuracy")
        self.logger.info(f"Developer: {__author__}")
        self.logger.info(f"Mode: {'DRY-RUN (No Changes)' if dry_run else 'ACTIVE'}")
        self.logger.info(f"{'='*80}")
    
    def _setup_logging(self):
        """Configure logging with file and console handlers"""
        log_file = self.log_dir / "ntp_optimizer.log"
        
        # Create logger
        self.logger = logging.getLogger("NTPOptimizer")
        self.logger.setLevel(getattr(logging, self.config['logging']['level']))
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        
        # Watermark in log
        self.logger.info(f"Log initialized by {__author__}")
    
    def check_root(self) -> bool:
        """Verify script is running with root privileges"""
        if os.geteuid() != 0:
            self.logger.error("This script must be run as root or with sudo privileges")
            self.logger.error("Please run: sudo python3 ntp_optimizer.py")
            return False
        return True
    
    def detect_geographic_region(self) -> Tuple[str, str]:
        """
        Detect geographic region from system timezone
        
        Returns:
            Tuple of (continent, region_code) e.g., ('asia', 'in')
            
        Developer: subhanigori@gmail.com - Auto-detection based on locale
        """
        self.logger.info("Detecting geographic region from system timezone...")
        
        try:
            # Try timedatectl first (modern systems)
            result = subprocess.run(
                ['timedatectl', 'show', '--property=Timezone'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                match = re.search(r'Timezone=(.*)', result.stdout)
                if match:
                    timezone = match.group(1).strip()
                    self.logger.info(f"  Detected timezone: {timezone}")
                    
                    # Parse timezone (e.g., "Asia/Kolkata" -> asia, in)
                    parts = timezone.split('/')
                    if len(parts) >= 1:
                        continent = parts[0].lower()
                        
                        # Map timezone to NTP pool region codes
                        region_map = {
                            'asia': 'asia',
                            'europe': 'europe',
                            'america': 'north-america',
                            'africa': 'africa',
                            'australia': 'oceania',
                            'oceania': 'oceania',
                        }
                        
                        # Map specific countries for better targeting
                        country_map = {
                            'kolkata': 'in',  # India
                            'tokyo': 'jp',    # Japan
                            'shanghai': 'cn', # China
                            'london': 'uk',   # UK
                            'paris': 'fr',    # France
                            'new_york': 'us', # US
                            'chicago': 'us',  # US
                            'los_angeles': 'us', # US
                        }
                        
                        region = region_map.get(continent, 'pool')
                        
                        # Try to get country code from city
                        if len(parts) >= 2:
                            city = parts[1].lower().replace('_', '_')
                            for key, code in country_map.items():
                                if key in city:
                                    self.logger.info(f"  Mapped to region: {region}, country: {code}")
                                    return (region, code)
                        
                        self.logger.info(f"  Mapped to region: {region}")
                        return (region, '')
            
            # Fallback: check /etc/timezone
            timezone_file = Path('/etc/timezone')
            if timezone_file.exists():
                timezone = timezone_file.read_text().strip()
                self.logger.info(f"  Detected timezone from /etc/timezone: {timezone}")
                parts = timezone.split('/')
                if parts:
                    continent = parts[0].lower()
                    region_map = {
                        'asia': 'asia',
                        'europe': 'europe',
                        'america': 'north-america',
                        'africa': 'africa',
                        'australia': 'oceania',
                    }
                    region = region_map.get(continent, 'pool')
                    return (region, '')
            
        except Exception as e:
            self.logger.warning(f"Could not auto-detect region: {e}")
        
        self.logger.info("  Using global pool as fallback")
        return ('pool', '')
    
    def detect_ntp_service(self) -> bool:
        """
        Detect which NTP service is installed and running
        
        Returns:
            bool: True if NTP service detected, False otherwise
            
        Developer: subhanigori@gmail.com
        """
        self.logger.info("Detecting NTP service...")
        
        # Check for chronyd (recommended for modern systems)
        if self._command_exists("chronyd") or self._command_exists("chronyc"):
            self.ntp_service = "chronyd"
            self.ntp_config_file = "/etc/chrony.conf"
            if not Path(self.ntp_config_file).exists():
                self.ntp_config_file = "/etc/chrony/chrony.conf"
            self.logger.info(f"✓ Detected NTP service: chronyd")
            self.logger.info(f"  Config file: {self.ntp_config_file}")
            return True
        
        # Check for ntpd
        if self._command_exists("ntpd") or self._command_exists("ntpq"):
            self.ntp_service = "ntpd"
            self.ntp_config_file = "/etc/ntp.conf"
            self.logger.info(f"✓ Detected NTP service: ntpd")
            self.logger.info(f"  Config file: {self.ntp_config_file}")
            return True
        
        # Check for systemd-timesyncd
        if self._command_exists("timedatectl"):
            result = subprocess.run(
                ["systemctl", "is-active", "systemd-timesyncd"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 or "active" in result.stdout:
                self.ntp_service = "systemd-timesyncd"
                self.ntp_config_file = "/etc/systemd/timesyncd.conf"
                self.logger.info(f"✓ Detected NTP service: systemd-timesyncd")
                self.logger.info(f"  Config file: {self.ntp_config_file}")
                return True
        
        self.logger.error("✗ No NTP service detected!")
        self.logger.error("")
        self.logger.error("Please install one of the following NTP services:")
        self.logger.error("  1. chronyd (RECOMMENDED):")
        self.logger.error("     RHEL/CentOS/Fedora: sudo dnf install chrony")
        self.logger.error("     Ubuntu/Debian:      sudo apt install chrony")
        self.logger.error("")
        self.logger.error("  2. ntpd (Traditional):")
        self.logger.error("     RHEL/CentOS/Fedora: sudo dnf install ntp")
        self.logger.error("     Ubuntu/Debian:      sudo apt install ntp")
        self.logger.error("")
        self.logger.error("  3. systemd-timesyncd (Basic):")
        self.logger.error("     Usually pre-installed with systemd")
        self.logger.error("")
        return False
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        result = subprocess.run(
            ["which", command],
            capture_output=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    
    def check_dependencies(self) -> bool:
        """
        Check and install required dependencies
        
        Returns:
            bool: True if all dependencies satisfied
            
        Developer: subhanigori@gmail.com
        """
        self.logger.info("Checking dependencies...")
        
        required_packages = {
            'deb': ['ntpdate', 'curl'],
            'rpm': ['ntpdate', 'curl']
        }
        
        # Detect package manager
        pkg_manager = None
        pkg_type = None
        
        if self._command_exists("apt"):
            pkg_manager = "apt"
            pkg_type = "deb"
        elif self._command_exists("dnf"):
            pkg_manager = "dnf"
            pkg_type = "rpm"
        elif self._command_exists("yum"):
            pkg_manager = "yum"
            pkg_type = "rpm"
        else:
            self.logger.error("Could not detect package manager (apt/dnf/yum)")
            return False
        
        self.logger.info(f"  Package manager: {pkg_manager}")
        
        # Check and install system packages
        missing_packages = []
        for package in required_packages[pkg_type]:
            if not self._command_exists(package):
                missing_packages.append(package)
        
        if missing_packages:
            self.logger.info(f"  Installing missing packages: {', '.join(missing_packages)}")
            if not self.dry_run:
                try:
                    if pkg_manager == "apt":
                        subprocess.run(
                            ["apt", "update"],
                            check=True,
                            capture_output=True,
                            timeout=120
                        )
                        subprocess.run(
                            ["apt", "install", "-y"] + missing_packages,
                            check=True,
                            capture_output=True,
                            timeout=300
                        )
                    else:
                        subprocess.run(
                            [pkg_manager, "install", "-y"] + missing_packages,
                            check=True,
                            capture_output=True,
                            timeout=300
                        )
                    self.logger.info("  ✓ System packages installed successfully")
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"  ✗ Failed to install packages: {e}")
                    return False
                except subprocess.TimeoutExpired:
                    self.logger.error("  ✗ Package installation timed out")
                    return False
        else:
            self.logger.info("  ✓ All system packages are installed")
        
        return True
    
    def fetch_ntp_servers(self) -> List[str]:
        """
        Fetch list of NTP servers with regional preference
        
        Returns:
            List of NTP server hostnames
            
        Developer: subhanigori@gmail.com - Regional optimization
        """
        self.logger.info("Fetching NTP server list...")
        servers = set()
        
        # Detect region if auto-detection enabled
        if self.config['geographic']['auto_detect']:
            self.detected_continent, self.detected_region = self.detect_geographic_region()
        
        # Try fetching from primary source
        try:
            import requests
            primary_url = self.config['server_sources'][0]
            response = requests.get(primary_url, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                pattern = r'(?:^|\s)([a-z0-9][-a-z0-9.]+\.[a-z]{2,})'
                matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    if 'ntp' in match.lower() or 'time' in match.lower():
                        servers.add(match.strip())
                self.logger.info(f"  ✓ Fetched {len(servers)} servers from primary source")
        except Exception as e:
            self.logger.warning(f"  ✗ Could not fetch from primary source: {e}")
        
        # Add regional servers based on detected location
        regional_servers = []
        if self.config['geographic']['prefer_regional'] and self.detected_continent:
            regional_servers = [
                f"0.{self.detected_continent}.pool.ntp.org",
                f"1.{self.detected_continent}.pool.ntp.org",
                f"2.{self.detected_continent}.pool.ntp.org",
                f"3.{self.detected_continent}.pool.ntp.org",
            ]
            servers.update(regional_servers)
            self.logger.info(f"  ✓ Added {len(regional_servers)} regional servers for {self.detected_continent}")
        
        # Add well-known reliable servers (global fallback)
        fallback_servers = [
            'time.cloudflare.com',     # Anycast, very reliable
            'time.google.com',         # Anycast, stratum 1
            'time.apple.com',          # Reliable
            'time.windows.com',        # Microsoft
            'time.nist.gov',           # US government
            'pool.ntp.org',           # Global pool
            '0.pool.ntp.org',
            '1.pool.ntp.org',
            '2.pool.ntp.org',
            '3.pool.ntp.org',
        ]
        
        if self.config['geographic']['fallback_to_global']:
            servers.update(fallback_servers)
            self.logger.info(f"  ✓ Added {len(fallback_servers)} global fallback servers")
        
        # Apply whitelist if configured
        if self.config['advanced']['whitelist']:
            whitelist = set(self.config['advanced']['whitelist'])
            servers = servers.intersection(whitelist)
            self.logger.info(f"  ⓘ Applied whitelist, {len(servers)} servers remain")
        
        # Remove blacklisted servers
        if self.blacklist:
            before = len(servers)
            servers = servers - self.blacklist
            removed = before - len(servers)
            if removed > 0:
                self.logger.info(f"  ⓘ Removed {removed} blacklisted servers")
        
        # Limit to configured maximum
        max_servers = self.config['testing']['max_servers_to_test']
        server_list = list(servers)[:max_servers]
        
        self.logger.info(f"  Total servers to test: {len(server_list)}")
        return server_list
    
    def test_ntp_server(self, hostname: str) -> Optional[NTPServer]:
        """
        Test a single NTP server for performance metrics
        
        Args:
            hostname: NTP server hostname or IP
            
        Returns:
            NTPServer object with test results or None if test failed
            
        Developer: subhanigori@gmail.com
        """
        samples = self.config['testing']['samples_per_server']
        timeout = self.config['testing']['timeout']
        
        offsets = []
        successful_tests = 0
        stratum = 16  # Default (invalid)
        
        for i in range(samples):
            try:
                result = subprocess.run(
                    ['ntpdate', '-q', hostname],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'offset' in line:
                            parts = line.split(',')
                            for part in parts:
                                if 'offset' in part:
                                    offset = float(part.split()[1])
                                    offsets.append(abs(offset) * 1000)  # Convert to ms
                                    successful_tests += 1
                                if 'stratum' in part:
                                    stratum = int(part.split()[1])
                                break
            except subprocess.TimeoutExpired:
                continue
            except Exception:
                continue
        
        if not offsets:
            return None
        
        # Calculate metrics
        avg_offset = statistics.mean(offsets)
        jitter = statistics.stdev(offsets) if len(offsets) > 1 else 0.0
        reachability = (successful_tests / samples) * 100
        
        return NTPServer(
            hostname=hostname,
            offset=round(avg_offset, 3),
            jitter=round(jitter, 3),
            stratum=stratum,
            reachability=round(reachability, 1),
            tested=True,
            region=self.detected_continent or 'global'
        )
    
    def calculate_score(self, server: NTPServer) -> float:
        """
        Calculate weighted score for NTP server
        Optimized for reliability and accuracy (client server use)
        
        Args:
            server: NTPServer object
            
        Returns:
            Score (0-100, higher is better)
            
        Developer: subhanigori@gmail.com - Reliability & Accuracy focus
        """
        weights = self.config['selection']
        
        # Normalize metrics to 0-100 scale
        
        # Jitter: 0-20ms range, lower is better (high weight for reliability)
        jitter_score = max(0, 100 - (server.jitter / 20 * 100))
        
        # Reachability: already 0-100, higher is better (high weight for reliability)
        reach_score = server.reachability
        
        # Stratum: 1-4 range, lower is better (high weight for accuracy)
        stratum_score = max(0, 100 - ((server.stratum - 1) / 3 * 100))
        
        # Offset: 0-50ms range, lower is better (lower weight for client use)
        offset_score = max(0, 100 - (server.offset / 50 * 100))
        
        # Calculate weighted score with reliability & accuracy focus
        score = (
            jitter_score * weights['weight_jitter'] +
            reach_score * weights['weight_reachability'] +
            stratum_score * weights['weight_stratum'] +
            offset_score * weights['weight_latency']
        )
        
        # Bonus for regional servers (lower latency, more reliable)
        if self.detected_continent and self.detected_continent in server.hostname:
            score *= 1.05  # 5% bonus
        
        return round(min(100, score), 2)
    
    def test_all_servers(self, servers: List[str]) -> List[NTPServer]:
        """
        Test all NTP servers and return sorted results
        
        Args:
            servers: List of server hostnames
            
        Returns:
            List of NTPServer objects sorted by score
            
        Developer: subhanigori@gmail.com
        """
        self.logger.info(f"Testing {len(servers)} NTP servers (this may take several minutes)...")
        
        tested_servers = []
        failures = {}
        
        # Test current server first if configured
        current_server = None
        if self.config['advanced']['test_current_first']:
            current_server = self.get_current_ntp_server()
            if current_server and current_server in servers:
                self.logger.info(f"Testing current server first: {current_server}")
                result = self.test_ntp_server(current_server)
                if result:
                    result.score = self.calculate_score(result)
                    tested_servers.append(result)
                    self.logger.info(
                        f"  ✓ Current: {result.hostname} | "
                        f"Offset: {result.offset}ms, Jitter: {result.jitter}ms, "
                        f"Stratum: {result.stratum}, Reach: {result.reachability}%, "
                        f"Score: {result.score}"
                    )
                servers.remove(current_server)
        
        # Test remaining servers
        for i, hostname in enumerate(servers, 1):
            self.logger.info(f"Testing {i}/{len(servers)}: {hostname}")
            server = self.test_ntp_server(hostname)
            
            if server:
                # Check stratum constraints
                if (server.stratum < self.config['selection']['min_stratum'] or 
                    server.stratum > self.config['selection']['max_stratum']):
                    self.logger.warning(
                        f"  ✗ {hostname} - Stratum {server.stratum} outside acceptable range "
                        f"({self.config['selection']['min_stratum']}-{self.config['selection']['max_stratum']})"
                    )
                    continue
                
                server.score = self.calculate_score(server)
                tested_servers.append(server)
                self.logger.info(
                    f"  ✓ Offset: {server.offset}ms, Jitter: {server.jitter}ms, "
                    f"Stratum: {server.stratum}, Reach: {server.reachability}%, "
                    f"Score: {server.score}"
                )
            else:
                self.logger.warning(f"  ✗ {hostname} - Failed to respond")
                failures[hostname] = failures.get(hostname, 0) + 1
                
                # Blacklist after repeated failures
                if failures[hostname] >= self.config['advanced']['blacklist_after_failures']:
                    self.blacklist.add(hostname)
                    self.logger.warning(f"  ⚠ Blacklisted {hostname} after {failures[hostname]} failures")
        
        # Save blacklist
        self._save_blacklist()
        
        # Sort by score (descending) - best first
        tested_servers.sort(key=lambda x: x.score, reverse=True)
        
        # Log results table
        self._log_results_table(tested_servers)
        
        return tested_servers
    
    def _log_results_table(self, servers: List[NTPServer]):
        """Log formatted table of test results"""
        self.logger.info("\n" + "="*100)
        self.logger.info("NTP SERVER PERFORMANCE TEST RESULTS")
        self.logger.info("Optimized for Reliability & Accuracy (Client Server Configuration)")
        self.logger.info(f"Developer: {__author__}")
        self.logger.info("="*100)
        
        header = (
            f"{'Rank':<6}{'Server':<35}{'Offset(ms)':<12}{'Jitter(ms)':<12}"
            f"{'Stratum':<10}{'Reach(%)':<10}{'Score':<8}"
        )
        self.logger.info(header)
        self.logger.info("-"*100)
        
        for i, server in enumerate(servers[:20], 1):  # Top 20
            row = (
                f"{i:<6}"
                f"{server.hostname:<35}"
                f"{server.offset:<12.3f}"
                f"{server.jitter:<12.3f}"
                f"{server.stratum:<10}"
                f"{server.reachability:<10.1f}"
                f"{server.score:<8.2f}"
            )
            self.logger.info(row)
        
        self.logger.info("="*100 + "\n")
    
    def get_current_ntp_server(self) -> Optional[str]:
        """Get currently configured NTP server"""
        try:
            if self.ntp_service == "chronyd":
                with open(self.ntp_config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('server') or line.startswith('pool'):
                            parts = line.split()
                            if len(parts) >= 2:
                                return parts[1]
            elif self.ntp_service == "ntpd":
                with open(self.ntp_config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('server'):
                            parts = line.split()
                            if len(parts) >= 2:
                                return parts[1]
            elif self.ntp_service == "systemd-timesyncd":
                result = subprocess.run(
                    ['timedatectl', 'show-timesync', '--property=ServerName'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    match = re.search(r'ServerName=(.*)', result.stdout)
                    if match:
                        return match.group(1).strip()
        except Exception as e:
            self.logger.warning(f"Could not determine current NTP server: {e}")
        
        return None
    
    def update_ntp_config(self, server: NTPServer) -> bool:
        """
        Update NTP configuration with new server
        
        Args:
            server: NTPServer object to configure
            
        Returns:
            bool: True if successful
            
        Developer: subhanigori@gmail.com
        """
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] Would update NTP config to: {server.hostname}")
            self.logger.info(f"[DRY-RUN] Score: {server.score}, Stratum: {server.stratum}")
            return True
        
        current_server = self.get_current_ntp_server()
        
        if current_server == server.hostname:
            self.logger.info(f"Server {server.hostname} is already configured (no change needed)")
            return True
        
        self.logger.info(f"Updating NTP configuration...")
        self.logger.info(f"  Current server: {current_server}")
        self.logger.info(f"  New server: {server.hostname}")
        self.logger.info(f"  New server score: {server.score}")
        self.logger.info(f"  New server stratum: {server.stratum}")
        
        try:
            # Backup current config
            if self.config['advanced']['backup_configs']:
                backup_file = f"{self.ntp_config_file}.backup.{int(time.time())}"
                subprocess.run(['cp', self.ntp_config_file, backup_file], check=True)
                self.logger.info(f"  ✓ Backed up config to: {backup_file}")
                
                # Clean up old backups
                self._cleanup_old_backups()
            
            # Update configuration based on service
            if self.ntp_service == "chronyd":
                self._update_chrony_config(server.hostname)
            elif self.ntp_service == "ntpd":
                self._update_ntpd_config(server.hostname)
            elif self.ntp_service == "systemd-timesyncd":
                self._update_timesyncd_config(server.hostname)
            
            self.logger.info(f"  ✓ Configuration file updated")
            
            # Restart service
            self.logger.info(f"  Restarting {self.ntp_service}...")
            subprocess.run(['systemctl', 'restart', self.ntp_service], check=True)
            time.sleep(3)
            
            # Verify service is running
            result = subprocess.run(
                ['systemctl', 'is-active', self.ntp_service],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info(f"  ✓ {self.ntp_service} restarted successfully")
            else:
                raise Exception(f"{self.ntp_service} failed to start")
            
            self.logger.info("✓ NTP configuration updated successfully")
            
            # Send email notification if enabled
            self._send_notification(
                subject=f"NTP Server Changed: {server.hostname}",
                message=(
                    f"NTP server has been updated:\n\n"
                    f"Previous: {current_server}\n"
                    f"New: {server.hostname}\n"
                    f"Score: {server.score}\n"
                    f"Stratum: {server.stratum}\n"
                    f"Offset: {server.offset}ms\n"
                    f"Jitter: {server.jitter}ms\n"
                    f"Reachability: {server.reachability}%\n\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"✗ Failed to update NTP config: {e}")
            
            # Attempt to restore backup
            if self.config['advanced']['backup_configs']:
                try:
                    self.logger.info("  Attempting to restore previous configuration...")
                    subprocess.run(['cp', backup_file, self.ntp_config_file], check=True)
                    subprocess.run(['systemctl', 'restart', self.ntp_service], check=True)
                    self.logger.info("  ✓ Restored previous configuration")
                except:
                    self.logger.error("  ✗ Failed to restore backup")
            
            # Send error notification
            self._send_notification(
                subject="NTP Optimizer Error",
                message=f"Failed to update NTP configuration:\n\n{str(e)}",
                is_error=True
            )
            
            return False
    
    def _cleanup_old_backups(self):
        """Remove old backup files, keeping only the most recent ones"""
        max_backups = self.config['advanced']['max_backups']
        backup_pattern = f"{self.ntp_config_file}.backup.*"
        
        backup_files = sorted(
            Path(self.ntp_config_file).parent.glob(f"{Path(self.ntp_config_file).name}.backup.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Remove old backups
        for old_backup in backup_files[max_backups:]:
            try:
                old_backup.unlink()
                self.logger.debug(f"  Removed old backup: {old_backup}")
            except:
                pass
    
    def _update_chrony_config(self, server: str):
        """Update chrony configuration"""
        with open(self.ntp_config_file, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        added = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('server') or stripped.startswith('pool'):
                if not added:
                    new_lines.append(f"server {server} iburst\n")
                    added = True
            else:
                new_lines.append(line)
        
        if not added:
            new_lines.insert(0, f"server {server} iburst\n")
        
        with open(self.ntp_config_file, 'w') as f:
            f.writelines(new_lines)
    
    def _update_ntpd_config(self, server: str):
        """Update ntpd configuration"""
        with open(self.ntp_config_file, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        added = False
        
        for line in lines:
            if line.strip().startswith('server'):
                if not added:
                    new_lines.append(f"server {server} iburst\n")
                    added = True
            else:
                new_lines.append(line)
        
        if not added:
            new_lines.insert(0, f"server {server} iburst\n")
        
        with open(self.ntp_config_file, 'w') as f:
            f.writelines(new_lines)
    
    def _update_timesyncd_config(self, server: str):
        """Update systemd-timesyncd configuration"""
        config_content = f"""# NTP Configuration - Managed by NTP Optimizer
# Developer: {__author__}
# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[Time]
NTP={server}
FallbackNTP=time.cloudflare.com time.google.com pool.ntp.org
"""
        with open(self.ntp_config_file, 'w') as f:
            f.write(config_content)
    
    def _load_blacklist(self):
        """Load blacklisted servers from file"""
        blacklist_file = self.data_dir / "blacklist.json"
        if blacklist_file.exists():
            try:
                with open(blacklist_file, 'r') as f:
                    data = json.load(f)
                    self.blacklist = set(data.get('servers', []))
            except:
                self.blacklist = set()
    
    def _save_blacklist(self):
        """Save blacklisted servers to file"""
        blacklist_file = self.data_dir / "blacklist.json"
        try:
            with open(blacklist_file, 'w') as f:
                json.dump({
                    'servers': list(self.blacklist),
                    'updated': datetime.now().isoformat()
                }, f, indent=2)
        except:
            pass
    
    def save_performance_history(self, servers: List[NTPServer]):
        """Save test results to history file"""
        history_file = self.data_dir / "server_history.json"
        
        timestamp = datetime.now().isoformat()
        entry = {
            'timestamp': timestamp,
            'region': self.detected_continent or 'global',
            'servers': [s.to_dict() for s in servers[:10]]  # Top 10
        }
        
        history = []
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(entry)
        
        # Keep only recent data
        retention_days = self.config['logging']['retention_days']
        cutoff = time.time() - (retention_days * 86400)
        history = [
            h for h in history
            if datetime.fromisoformat(h['timestamp']).timestamp() > cutoff
        ]
        
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
        
        self.logger.info(f"✓ Saved performance history to {history_file}")
    
    def _send_notification(self, subject: str, message: str, is_error: bool = False):
        """
        Send email notification
        
        Developer: subhanigori@gmail.com
        """
        email_config = self.config['notifications']['email']
        
        if not email_config['enabled']:
            return
        
        if is_error and not email_config['send_on_error']:
            return
        
        if not is_error and not email_config['send_on_change']:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = email_config['from_address']
            msg['To'] = ', '.join(email_config['to_addresses'])
            msg['Subject'] = f"[NTP Optimizer] {subject}"
            
            body = f"""
NTP Server Optimizer Notification
Developer: {__author__}

{message}

---
This is an automated message from NTP Server Optimizer v{__version__}
"""
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            if email_config['use_tls']:
                server.starttls()
            
            if email_config['username'] and email_config['password']:
                server.login(email_config['username'], email_config['password'])
            
            server.send_message(msg)
            server.quit()
            
            self.logger.info("✓ Email notification sent")
            
        except Exception as e:
            self.logger.warning(f"Could not send email notification: {e}")
    
    def setup_scheduler(self):
        """Setup systemd timer for periodic execution"""
        if self.dry_run:
            self.logger.info("[DRY-RUN] Would setup scheduler")
            return
        
        interval = self.config['testing']['interval_hours']
        script_path = Path(__file__).absolute()
        
        # Create systemd service
        service_content = f"""# NTP Server Optimizer Service
# Developer: {__author__}
# Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[Unit]
Description=NTP Server Optimizer - Client Server Time Sync Optimization
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {script_path} --no-schedule
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        # Create systemd timer
        timer_content = f"""# NTP Server Optimizer Timer
# Developer: {__author__}
# Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[Unit]
Description=NTP Server Optimizer Timer - Runs every {interval} hours
Requires=ntp-optimizer.service

[Timer]
OnBootSec=5min
OnUnitActiveSec={interval}h
AccuracySec=1min
Persistent=true

[Install]
WantedBy=timers.target
"""
        
        try:
            # Write service file
            with open('/etc/systemd/system/ntp-optimizer.service', 'w') as f:
                f.write(service_content)
            
            # Write timer file
            with open('/etc/systemd/system/ntp-optimizer.timer', 'w') as f:
                f.write(timer_content)
            
            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', 'enable', 'ntp-optimizer.timer'], check=True)
            subprocess.run(['systemctl', 'start', 'ntp-optimizer.timer'], check=True)
            
            self.logger.info(f"✓ Scheduled to run every {interval} hours")
            self.logger.info("  Manage with:")
            self.logger.info("    Status:  sudo systemctl status ntp-optimizer.timer")
            self.logger.info("    Stop:    sudo systemctl stop ntp-optimizer.timer")
            self.logger.info("    Start:   sudo systemctl start ntp-optimizer.timer")
            self.logger.info("    Disable: sudo systemctl disable ntp-optimizer.timer")
            
        except Exception as e:
            self.logger.warning(f"Could not setup systemd timer: {e}")
            self.logger.info("You can setup a cron job manually if needed")
    
    def run(self, setup_schedule: bool = True) -> bool:
        """
        Main execution flow
        
        Args:
            setup_schedule: Whether to setup periodic scheduling
            
        Returns:
            bool: True if successful
            
        Developer: subhanigori@gmail.com
        """
        try:
            start_time = time.time()
            
            # Check root privileges
            if not self.check_root():
                return False
            
            # Detect NTP service
            if not self.detect_ntp_service():
                return False
            
            # Check dependencies
            if not self.check_dependencies():
                return False
            
            # Fetch server list with regional optimization
            server_list = self.fetch_ntp_servers()
            if not server_list:
                self.logger.error("✗ Could not fetch NTP server list")
                return False
            
            # Test all servers
            tested_servers = self.test_all_servers(server_list)
            
            if not tested_servers:
                self.logger.error("✗ No servers responded to tests")
                return False
            
            # Save results
            self.save_performance_history(tested_servers)
            
            # Select best server
            best_server = tested_servers[0]
            min_score = self.config['selection']['min_score']
            
            if best_server.score < min_score:
                self.logger.warning(
                    f"⚠ Best server score ({best_server.score}) below minimum threshold ({min_score})"
                )
                self.logger.warning("  Keeping current configuration")
                return True
            
            # Check hysteresis - don't switch if current is close enough
            current_server_name = self.get_current_ntp_server()
            if current_server_name:
                current_server_obj = next((s for s in tested_servers if s.hostname == current_server_name), None)
                if current_server_obj:
                    score_diff = best_server.score - current_server_obj.score
                    hysteresis = self.config['selection']['hysteresis_percent']
                    if score_diff < hysteresis:
                        self.logger.info(
                            f"Current server {current_server_name} (score: {current_server_obj.score}) "
                            f"is within {hysteresis}% of best server (score: {best_server.score})"
                        )
                        self.logger.info("✓ Keeping current configuration (hysteresis threshold)")
                        return True
            
            # Log selected server
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"SELECTED OPTIMAL SERVER FOR CLIENT CONFIGURATION")
            self.logger.info(f"{'='*80}")
            self.logger.info(f"  Server: {best_server.hostname}")
            self.logger.info(f"  Score: {best_server.score} (Reliability & Accuracy optimized)")
            self.logger.info(f"  Stratum: {best_server.stratum} (Distance from atomic clock)")
            self.logger.info(f"  Jitter: {best_server.jitter}ms (Stability)")
            self.logger.info(f"  Reachability: {best_server.reachability}% (Reliability)")
            self.logger.info(f"  Offset: {best_server.offset}ms (Latency)")
            self.logger.info(f"  Region: {best_server.region}")
            self.logger.info(f"{'='*80}\n")
            
            # Update configuration
            if not self.update_ntp_config(best_server):
                return False
            
            # Setup scheduler if requested
            if setup_schedule:
                self.setup_scheduler()
            
            # Calculate execution time
            elapsed = time.time() - start_time
            
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"✓ NTP OPTIMIZATION COMPLETED SUCCESSFULLY")
            self.logger.info(f"  Execution time: {elapsed:.1f} seconds")
            self.logger.info(f"  Developer: {__author__}")
            self.logger.info(f"  Version: {__version__}")
            self.logger.info(f"{'='*80}\n")
            
            return True
            
        except KeyboardInterrupt:
            self.logger.info("\n\nOperation cancelled by user")
            return False
        except Exception as e:
            self.logger.error(f"✗ Unexpected error: {e}", exc_info=True)
            self._send_notification(
                subject="NTP Optimizer Fatal Error",
                message=f"Fatal error occurred:\n\n{str(e)}",
                is_error=True
            )
            return False


def main():
    """
    Main entry point
    
    Developer: subhanigori@gmail.com
    """
    parser = argparse.ArgumentParser(
        description=f"NTP Server Optimizer v{__version__} - Enterprise Edition\n"
                    f"Optimized for Client Server Reliability & Accuracy\n"
                    f"Developer: {__author__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 ntp_optimizer.py                    # Run with default settings
  sudo python3 ntp_optimizer.py --dry-run          # Test without making changes
  sudo python3 ntp_optimizer.py --no-schedule      # Run once, don't setup timer
  sudo python3 ntp_optimizer.py --interval 12      # Custom interval (12 hours)
  
Configuration:
  Edit the CONFIG dictionary at the top of this file to customize:
  - Testing frequency (interval_hours)
  - Server selection weights (reliability vs speed)
  - Email notifications
  - Geographic preferences
  - And more...

Support:
  Developer: subhanigori@gmail.com
  Report issues on GitHub
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test without making actual changes to system'
    )
    
    parser.add_argument(
        '--no-schedule',
        action='store_true',
        help='Do not setup periodic scheduling (one-time run)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        metavar='HOURS',
        help='Override default testing interval (hours)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'NTP Optimizer {__version__} by {__author__}'
    )
    
    args = parser.parse_args()
    
    # Print banner
    print(f"\n{'='*80}")
    print(f"  NTP Server Optimizer v{__version__} - Enterprise Edition")
    print(f"  Optimized for Client Server Reliability & Accuracy")
    print(f"  Developer: {__author__}")
    print(f"  {__copyright__}")
    print(f"{'='*80}\n")
    
    # Apply command-line overrides
    config = CONFIG.copy()
    if args.interval:
        config['testing']['interval_hours'] = args.interval
        print(f"Using custom interval: {args.interval} hours\n")
    
    # Create and run optimizer
    optimizer = NTPOptimizer(
        config=config,
        dry_run=args.dry_run
    )
    
    success = optimizer.run(setup_schedule=not args.no_schedule)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

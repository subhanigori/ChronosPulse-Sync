#!/bin/bash
#
# NTP Server Optimizer - Installation Script (Enterprise Edition)
# Developer: subhanigori@gmail.com
# Version: 2.0.0
# Copyright (c) 2024 subhanigori@gmail.com
#
# This script installs all dependencies and sets up the NTP optimizer
# Optimized for client server reliability and accuracy
#

set -e

echo "================================================================================"
echo "  NTP Server Optimizer v2.0.0 - Enterprise Edition"
echo "  Installation Script"
echo "  Optimized for Client Server Reliability & Accuracy"
echo "  Developer: subhanigori@gmail.com"
echo "================================================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root or with sudo"
    echo "Please run: sudo ./install.sh"
    exit 1
fi

echo "[1/8] Detecting system..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
    echo "  ✓ Detected: $PRETTY_NAME"
else
    echo "  ✗ ERROR: Cannot detect operating system"
    exit 1
fi

# Detect package manager
echo ""
echo "[2/8] Detecting package manager..."
if command -v apt >/dev/null 2>&1; then
    PKG_MGR="apt"
    PKG_UPDATE="apt update"
    PKG_INSTALL="apt install -y"
    PYTHON_PKG="python3 python3-pip"
    echo "  ✓ Using: apt (Debian/Ubuntu family)"
elif command -v dnf >/dev/null 2>&1; then
    PKG_MGR="dnf"
    PKG_UPDATE="dnf check-update || true"
    PKG_INSTALL="dnf install -y"
    PYTHON_PKG="python3 python3-pip"
    echo "  ✓ Using: dnf (RHEL/Fedora family)"
elif command -v yum >/dev/null 2>&1; then
    PKG_MGR="yum"
    PKG_UPDATE="yum check-update || true"
    PKG_INSTALL="yum install -y"
    PYTHON_PKG="python3 python3-pip"
    echo "  ✓ Using: yum (CentOS/RHEL family)"
else
    echo "  ✗ ERROR: No supported package manager found (apt/dnf/yum)"
    exit 1
fi

echo ""
echo "[3/8] Updating package cache..."
$PKG_UPDATE

echo ""
echo "[4/8] Installing Python..."
PACKAGES="$PYTHON_PKG"
echo "  Installing: $PACKAGES"
$PKG_INSTALL $PACKAGES

echo ""
echo "[5/8] Installing system dependencies..."
PACKAGES="ntpdate curl"
echo "  Installing: $PACKAGES"
$PKG_INSTALL $PACKAGES

echo ""
echo "[6/8] Checking for NTP service..."
NTP_INSTALLED=false

if command -v chronyd >/dev/null 2>&1 || command -v chronyc >/dev/null 2>&1; then
    echo "  ✓ Found: chronyd (recommended)"
    NTP_INSTALLED=true
elif command -v ntpd >/dev/null 2>&1; then
    echo "  ✓ Found: ntpd"
    NTP_INSTALLED=true
elif command -v timedatectl >/dev/null 2>&1; then
    if systemctl is-active --quiet systemd-timesyncd; then
        echo "  ✓ Found: systemd-timesyncd"
        NTP_INSTALLED=true
    fi
fi

if [ "$NTP_INSTALLED" = false ]; then
    echo "  ⚠ No NTP service found. Installing chronyd (recommended)..."
    $PKG_INSTALL chrony
    systemctl enable chronyd
    systemctl start chronyd
    echo "  ✓ chronyd installed and started"
fi

echo ""
echo "[7/8] Installing Python dependencies..."
pip3 install --upgrade pip --quiet
pip3 install requests --quiet

echo ""
echo "[8/8] Setting up directories..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/data"
chmod 755 "$SCRIPT_DIR/ntp_optimizer.py"

# Make script executable
if [ -f "$SCRIPT_DIR/ntp_optimizer.py" ]; then
    chmod +x "$SCRIPT_DIR/ntp_optimizer.py"
fi

echo ""
echo "================================================================================"
echo "  ✓ INSTALLATION COMPLETED SUCCESSFULLY"
echo "================================================================================"
echo ""
echo "Configuration:"
echo "  All settings can be customized by editing the CONFIG section in:"
echo "  $SCRIPT_DIR/ntp_optimizer.py"
echo ""
echo "  Key settings:"
echo "    - Testing interval: interval_hours (default: 6 hours)"
echo "    - Server selection weights (optimized for reliability & accuracy)"
echo "    - Email notifications (disabled by default)"
echo "    - Geographic preferences (auto-detected)"
echo ""
echo "Next steps:"
echo ""
echo "  1. (Recommended) Test without making changes:"
echo "     sudo python3 ntp_optimizer.py --dry-run"
echo ""
echo "  2. Run the optimizer:"
echo "     sudo python3 ntp_optimizer.py"
echo ""
echo "  3. Run with custom interval (e.g., every 12 hours):"
echo "     sudo python3 ntp_optimizer.py --interval 12"
echo ""
echo "  4. Run once without scheduling:"
echo "     sudo python3 ntp_optimizer.py --no-schedule"
echo ""
echo "  5. View help and all options:"
echo "     python3 ntp_optimizer.py --help"
echo ""
echo "  6. Check logs after running:"
echo "     tail -f logs/ntp_optimizer.log"
echo ""
echo "  7. Manage scheduled runs:"
echo "     sudo systemctl status ntp-optimizer.timer"
echo "     sudo systemctl stop ntp-optimizer.timer"
echo "     sudo systemctl start ntp-optimizer.timer"
echo ""
echo "Documentation:"
echo "  - View configuration options: Open ntp_optimizer.py and see CONFIG section"
echo "  - Check performance history: cat data/server_history.json"
echo ""
echo "Support:"
echo "  Developer: subhanigori@gmail.com"
echo "  Report issues on GitHub"
echo ""
echo "================================================================================"
echo "  Ready to optimize your NTP configuration!"
echo "  Developer: subhanigori@gmail.com"
echo "================================================================================"

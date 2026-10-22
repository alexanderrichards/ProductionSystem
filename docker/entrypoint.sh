#!/usr/bin/env bash
#
# Entry point script for setting up DIRAC VO proxy and updating VOMS users
set -euo pipefail

# Source DIRAC environment
source /root/dirac_ui/diracos/diracosrc

# Create vo based proxy
dirac-proxy-init -g gridpp_user -M

# Update VOMS Users - this cant be done at build time as it need the database to be up
userdb-update.py

exec bash -c "$*" bash "$@"

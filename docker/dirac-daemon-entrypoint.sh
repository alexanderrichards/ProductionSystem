#!/bin/bash
set -euo pipefail

# Ensure certs exist
if [[ ! -f /root/.globus/usercert.pem ]]; then
    echo "Missing usercert.pem"
    exit 1
fi

if [[ ! -f /root/.globus/userkey.pem ]]; then
    echo "Missing userkey.pem"
    exit 1
fi

# Source DIRAC environment
source /root/dirac_ui/diracos/diracosrc

# Initialise DIRAC proxy  -  must be unencrypted key.pem file
dirac-proxy-init -x -N

# Configure DIRAC
dirac-configure -F -S GridPP -C dips://dirac01.grid.hep.ph.ic.ac.uk:9135/Configuration/Server -I

# Generate self-signed host certificate for grid-security
openssl req -x509 -newkey rsa:2048 -keyout /root/dirac_ui/diracos/etc/grid-security/hostkey.pem -out /root/dirac_ui/diracos/etc/grid-security/hostcert.pem -days 365 -nodes -subj "/CN=myhost.test"

# check if the grid-security directory exists and if not, link it
echo "Checking if /etc/grid-security exists..."
if [[ ! -d /etc/grid-security  ]]; then
    echo "Setting up /etc/grid-security..."
    # Link DIRAC grid-security to expected location - This will fill the docker volume with the necessary grid-security files on first run
    ln -s /root/dirac_ui/diracos/etc/grid-security /etc/grid-security
fi

# Create vo based proxy
dirac-proxy-init -g gridpp_user -M

# Update VOMS Users
userdb-update.py

# Start daemon
exec dirac-daemon.py start --debug-mode

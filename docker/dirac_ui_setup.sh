#!/usr/bin/env bash
set -euo pipefail

DIRAC_VERSION="${1:-8.0.74}"
PRODUCTION_SYSTEM_VERSION="${2:-modern_python3_update}"

echo "Using DIRAC version: $DIRAC_VERSION"

mkdir dirac_ui
cd dirac_ui

curl -LO https://github.com/DIRACGrid/DIRACOS2/releases/latest/download/DIRACOS-Linux-$(uname -m).sh
bash DIRACOS-Linux-$(uname -m).sh
rm -f DIRACOS-Linux-$(uname -m).sh

source diracos/diracosrc
pip install "DIRAC==$DIRAC_VERSION"

python -m pip install --no-cache-dir --upgrade "git+https://github.com/alexanderrichards/ProductionSystem.git@$PRODUCTION_SYSTEM_VERSION"
# dirac-proxy-init -x -N
# dirac-configure -F -S GridPP -C dips://dirac01.grid.hep.ph.ic.ac.uk:9135/Configuration/Server -I

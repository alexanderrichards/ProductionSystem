#!/bin/sh
set -euo pipefail

cd /root

. ./dirac_ui/diracos/diracosrc

python -m pip install -e ProductionSystem/

mkdir -p /root/.config/productionsystem

ln -s /root/ProductionSystem/docker/productionsystem.conf /root/.config/productionsystem/productionsystem.conf

exec sh -c "$*" sh "$@"
#!/bin/sh
set -eu

cd /root

. "${PYTHON_ENV_ACTIVATE:-/root/venv/bin/activate}"

python -m pip install -e ProductionSystem/

exec sh -c "$*" sh "$@"
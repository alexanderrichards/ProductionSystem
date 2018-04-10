#!/bin/bash
. $HOME/git/ProductionSystem/venv/bin/activate
#$HOME/LZProduction/scripts/start-webserver.py -p18443 -d"mysql+pymysql://lzprod:JuvMoafcug2@localhost/lzprod"
$HOME/git/ProductionSystem/scripts/webapp-daemon.py -p8080

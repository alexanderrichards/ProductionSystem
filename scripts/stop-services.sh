#!/usr/bin/env bash
echo "*** Stopping services ***"
find $PWD -maxdepth 1 -iname "*.pid" -exec pkill -15 -L -F {} \;
#echo `dirname "$(readlink -f "$0")"`

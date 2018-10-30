#!/usr/bin/env bash
find $PWD -maxdepth 1 -iname "*.pid" -exec pkill -0 -L -F {} \; -exec basename -z {} .pid \; -exec echo " running" \;

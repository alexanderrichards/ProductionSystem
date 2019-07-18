#!/usr/bin/env bash

function start_daemon {
    case "$1" in
        dirac)
            echo "*** Starting DIRAC daemon. ***"
            (. /root/dirac_ui/bashrc && dirac-daemon.py start)
            ;;
        monitoring)
            echo "*** Starting monitoring daemon. ***"
            (. /root/venv3/bin/activate && monitoring-daemon.py start)
            ;;
        webapp)
            echo "*** Starting web app daemon. ***"
            (. /root/venv3/bin/activate && webapp-daemon.py start)
            ;;
        all)
            start_daemon dirac
            start_daemon monitoring
            start_daemon webapp
            ;;
        *)
            echo "Unknown parameter: $1"
            echo "Expected: {dirac|monitoring|webapp|all}"
            exit 1
    esac
}

start_daemon $1
/bin/bash

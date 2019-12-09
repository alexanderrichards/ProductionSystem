#!/bin/bash

trap "stop_daemon $1 && exit 0" SIGTERM

function stop_daemon {
    case "$1" in
        dirac)
            echo "*** Stopping DIRAC daemon. ***"
            (. /root/dirac_ui/bashrc && dirac-daemon.py stop)
            ;;
        monitoring)
            echo "*** Stopping monitoring daemon. ***"
            monitoring-daemon.py stop
            ;;
        webapp)
            echo "*** Stopping web app daemon. ***"
            webapp-daemon.py stop
            ;;
        all)
            stop_daemon dirac
            stop_daemon monitoring
            stop_daemon webapp
            ;;
        *)
            echo "Unknown parameter: $1"
            echo "Expected: {dirac|monitoring|webapp|all}"
            exit 1
    esac
}

function start_daemon {
    case "$1" in
        dirac)
            echo "*** Starting DIRAC daemon. ***"
            (. /root/dirac_ui/bashrc && dirac-daemon.py start)
            ;;
        monitoring)
            echo "*** Starting monitoring daemon. ***"
            monitoring-daemon.py start
            ;;
        webapp)
            echo "*** Starting web app daemon. ***"
            webapp-daemon.py start
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
# Allow time to receive and process SIGTERM handler
while true
do
sleep 5
done

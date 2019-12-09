#!/bin/bash
(. ~/dirac_ui/bashrc && dirac-proxy-init -x)
#DOCKER_BUILDKIT=1 docker build --no-cache --progress=plain --secret id=proxy,src=/tmp/x509up_u`id -u` -t alexanderrichards/productionsystem:latest .
DOCKER_BUILDKIT=1 docker build --progress=plain --secret id=proxy,src=/tmp/x509up_u`id -u` -t alexanderrichards/productionsystem:latest .

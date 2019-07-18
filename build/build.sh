#!/usr/bin/env bash
DOCKER_BUILDKIT=1 docker build --ssh default --no-cache --progress=plain --secret id=proxy,src=/tmp/x509up_u$ID -t alexanderrichards/productionsystem:latest .

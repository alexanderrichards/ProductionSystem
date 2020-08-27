# syntax = docker/dockerfile:1.0-experimental
ARG dirac_version=v6r22p26
FROM alexanderrichards/dirac_ui:${dirac_version}
ARG productionsystem_version=master

RUN yum install -y git gcc python3 python3-devel
RUN python3 -m pip install --upgrade pip setuptools wheel
RUN python3 -m pip install --upgrade productionsystem@git+https://github.com/alexanderrichards/ProductionSystem.git@$productionsystem_version
RUN yum clean all

## setup cron jobs - maybe not needed if mounting from outside.
RUN echo "@daily userdb-update.py &>> /root/log/userdb-update.log" | crontab

WORKDIR /root

COPY startup.sh /root/startup.sh

CMD ["all"]

ENTRYPOINT ["/root/startup.sh"]

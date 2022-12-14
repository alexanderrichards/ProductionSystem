# syntax = docker/dockerfile:1.0-experimental
ARG dirac_version=v6r22p26
FROM alexanderrichards/dirac_ui:${dirac_version}
ARG productionsystem_version=master

RUN yum install -y git gcc cronie python3 python3-devel yum-priorities
RUN yum install -y http://repository.egi.eu/sw/production/umd/4/centos7/x86_64/updates/umd-release-4.1.3-1.el7.centos.noarch.rpm
RUN yum install -y ca-policy-egi-core fetch-crl
RUN systemctl enable fetch-crl-cron; systemctl start fetch-crl-cron
RUN fetch-crl -v
RUN python3 -m pip install --upgrade pip setuptools wheel
RUN python3 -m pip install --upgrade productionsystem@git+https://github.com/alexanderrichards/ProductionSystem.git@$productionsystem_version
RUN . /root/dirac_ui/bashrc && python -m pip install --upgrade pip setuptools wheel && python -m pip install --upgrade productionsystem@git+https://github.com/alexanderrichards/ProductionSystem.git@$productionsystem_version
RUN yum clean all

## setup cron jobs - maybe not needed if mounting from outside.
RUN echo "@daily userdb-update.py &>> /root/log/userdb-update.log" | crontab
RUN echo -e "[userdb]\ntrusted_cas='/etc/grid-security/certificates'" > /root/.config/productionsystem/productionsystem.conf
WORKDIR /root

COPY startup.sh /root/startup.sh

CMD ["all"]

ENTRYPOINT ["/root/startup.sh"]

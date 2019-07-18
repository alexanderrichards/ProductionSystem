# syntax = docker/dockerfile:1.0-experimental
FROM centos:7
ARG dirac_version=v6r21p7
ARG lcgtools_version=v14r1
ARG python_version=27
ARG productionsystem_version=master

RUN yum install -y centos-release-scl
RUN yum install -y rh-python36
RUN yum install -y wget git gcc
RUN yum clean all

RUN mkdir -p /root/dirac_ui

WORKDIR /root/dirac_ui

RUN wget -np -O dirac-install https://raw.githubusercontent.com/DIRACGrid/DIRAC/integration/Core/scripts/dirac-install.py
RUN chmod u+x dirac-install
RUN ./dirac-install -r $dirac_version -i $python_version -g $lcgtools_version
RUN --mount=type=secret,id=proxy,dst=/tmp/x509up_u0 . /root/dirac_ui/bashrc && dirac-configure -F -S GridPP -C dips://dirac01.grid.hep.ph.ic.ac.uk:9135/Configuration/Server -I
RUN rm -f dirac-install

WORKDIR /root

RUN echo "virtualenv venv3" | scl enable rh-python36 -
RUN . venv3/bin/activate && pip install --upgrade pip setuptools wheel
RUN --mount=type=ssh . venv3/bin/activate && pip install productionsystem@git+git://github.com/alexanderrichards/ProductionSystem.git@$productionsystem_version
RUN . dirac_ui/bashrc && python -m pip install --upgrade pip setuptools wheel
RUN --mount=type=ssh . dirac_ui/bashrc && python -m pip install --upgrade productionsystem@git+git://github.com/alexanderrichards/ProductionSystem.git@$productionsystem_version

COPY startup.sh /root/startup.sh

CMD ["all"]

ENTRYPOINT ["/root/startup.sh"]

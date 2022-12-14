# syntax = docker/dockerfile:1.0-experimental
from centos:8
ARG dirac_version=v6r22p6
ARG lcgtools_version=v14r1
ARG python_version=27
ARG productionsystem_version=master

RUN dnf swap -y coreutils-single coreutils  # Fix for wrapper coreutils
RUN dnf install -y cronie gcc git wget python2 python3 python3-devel
RUN alternatives --set python /usr/bin/python2  # Set unversioned python command to python2 for DIRAC scripts
RUN python3 -m pip install --upgrade pip setuptools wheel
RUN python3 -m pip install --upgrade productionsystem@git+https://github.com/alexanderrichards/ProductionSystem.git@$productionsystem_version
RUN dnf clean all

# DIRAC setup
RUN mkdir -p /root/dirac_ui
WORKDIR /root/dirac_ui
RUN wget -np -O dirac-install https://raw.githubusercontent.com/DIRACGrid/DIRAC/integration/Core/scripts/dirac-install.py
RUN chmod u+x dirac-install
RUN ./dirac-install --dirac-os -r $dirac_version -i $python_version -g $lcgtools_version
RUN --mount=type=secret,id=proxy,dst=/tmp/x509up_u0 . /root/dirac_ui/bashrc && dirac-configure -F -S GridPP -C dips://dirac01.grid.hep.ph.ic.ac.uk:9135/Configuration/Server -I
# These two lines are necessary as git commands broken in DIRACOS so need to check out first then pip install else could do commented out line below
RUN git clone -b $productionsystem_version https://github.com/alexanderrichards/ProductionSystem.git
RUN . /root/dirac_ui/bashrc && python -m pip install --upgrade ProductionSystem/
#RUN . /root/dirac_ui/bashrc && python -m pip install -v --trusted-host github.com --upgrade productionsystem@git+https://github.com/alexanderrichards/ProductionSystem.git@$productionsystem_version
RUN rm -f dirac-install


## setup cron jobs - maybe not needed if mounting from outside.
RUN echo "@daily userdb-update.py &>> /root/log/userdb-update.log" | crontab

WORKDIR /root

COPY startup.sh /root/startup.sh

CMD ["all"]

ENTRYPOINT ["/root/startup.sh"]

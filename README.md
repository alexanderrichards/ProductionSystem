# ProductionSystem
[![Build Status](https://travis-ci.com/alexanderrichards/ProductionSystem.svg?branch=master)](https://travis-ci.com/alexanderrichards/ProductionSystem)
[![Documentation Status](https://readthedocs.org/projects/productionsystem/badge/?version=latest)](https://productionsystem.readthedocs.io/en/latest/?badge=latest)
---

The documentation for the RESTful API can be seen [here](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/alexanderrichards/ProductionSystem/master/docs/openapi/openapi.yaml)

## DIRAC environment API

Communication from the monitoring daemon to the DIRAC environment daemon uses
an internal FastAPI service. Start both daemons with matching endpoints:

```shell
dirac-daemon.py start --api-host localhost --api-port 18861
monitoring-daemon.py start --dirac-api-url http://localhost:18861
```

The service binds to localhost by default. Its generated OpenAPI documentation
is available at `http://localhost:18861/docs` while the daemon is running.

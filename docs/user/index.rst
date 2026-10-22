User and operator guide
=======================

This guide follows the complete path from obtaining access to submitting,
reviewing, and operating production workloads. Most request users only need
the first two chapters and, optionally, the automation chapter. Installation,
configuration, operations, and troubleshooting are intended for service owners.

.. toctree::
   :maxdepth: 2

   getting-started
   requests
   automation
   installation
   configuration
   operations
   troubleshooting

Conventions used in examples
-----------------------------

* ``https://production.example.org`` is a placeholder for your deployment's
  public HTTPS address, not a running service.
* Request ID ``42`` and parametric job ID ``1`` are examples. Substitute actual
  IDs after inspecting your own deployment.
* Paths under ``/srv/productionsystem`` are suggested Linux deployment paths,
  not directories created automatically by the package.
* Shell examples target Linux or a Linux container unless explicitly marked
  as PowerShell. Full daemon operation requires a POSIX environment.
* Example database credentials and certificate paths must be replaced locally.
  Do not commit working secrets or private keys.

For exact Python signatures, follow the separate :doc:`../productionsystem`
reference. For changes to the system itself, continue with the
:doc:`../developer/index`.

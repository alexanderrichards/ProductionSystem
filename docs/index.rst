.. Production System documentation master file, created by
   sphinx-quickstart on Fri Aug 17 14:50:47 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Production System documentation
===============================

Production System manages production requests, groups their work into
parametric jobs, and submits and monitors external jobs through DIRAC.
An authenticated web application and Python client provide access to the same
request workflow.

Start with the user guide if you submit or review requests. Operators should
also read the installation, configuration, and operations chapters. The
developer guide explains the architecture, extension contracts, and contribution
workflow. The API reference remains a separate description of Python objects
and command scripts.

.. note::

   These guides describe the built-in implementation in this repository.
   An installed experiment-specific extension can add fields, templates, and
   job-generation behavior. Obtain the extension's own instructions before
   submitting real workloads.

.. toctree::
   :maxdepth: 2
   :caption: User documentation

   user/index

.. toctree::
   :maxdepth: 2
   :caption: Developer documentation

   developer/index

.. toctree::
   :maxdepth: 2
   :caption: API reference

   productionsystem


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

productionsystem.suds\_utils module
===================================

.. automodule:: productionsystem.suds_utils
    :members:
    :undoc-members:
    :show-inheritance:

TLS configuration
-----------------

The suds transport, JSI client, and monitoring health check load X509 credentials
into an ``ssl.SSLContext`` passed to HTTPX via ``verify``. A client certificate
can be a combined PEM file or a ``(certificate_file, key_file)`` pair; it is not
passed as a per-request ``cert`` argument.

``verify=True`` uses system trust roots (including OpenSSL's ``SSL_CERT_FILE``
and ``SSL_CERT_DIR`` environment settings). A path selects a CA bundle file or
an OpenSSL hashed CA directory. ``verify=False`` disables server verification
but still loads the client certificate for mutual TLS authentication.

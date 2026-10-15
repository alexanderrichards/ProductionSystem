"""TLS configuration shared by certificate-authenticated HTTP clients."""

import os
import ssl


def create_ssl_context(cert: str | tuple[str, str] | None = None, verify: bool | str = True) -> ssl.SSLContext:
    """Build an HTTPX-compatible context with optional X509 client authentication.

    ``verify`` accepts a verification flag, a CA bundle file, or an OpenSSL
    hashed CA directory. Default trust roots and the ``SSL_CERT_FILE`` and
    ``SSL_CERT_DIR`` environment variables are handled by OpenSSL.
    ``cert`` accepts a combined PEM file or a ``(certificate, key)`` pair.
    """
    if verify is False:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif isinstance(verify, str):
        if os.path.isdir(verify):
            context = ssl.create_default_context(capath=verify)
        else:
            context = ssl.create_default_context(cafile=verify)
    else:
        context = ssl.create_default_context()

    if isinstance(cert, tuple):
        context.load_cert_chain(*cert)
    elif cert is not None:
        context.load_cert_chain(cert)
    return context

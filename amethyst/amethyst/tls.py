import datetime
import os.path
import logging
import ssl
import traceback

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


log = logging.getLogger("amethyst.tls")


def make_partial_context():
    c = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    c.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    c.options |= ssl.OP_SINGLE_DH_USE | ssl.OP_SINGLE_ECDH_USE
    c.check_hostname = False
    c.verify_mode = ssl.VerifyMode.CERT_OPTIONAL
    return c


def make_context(cert_path: str, key_path: str):
    c = make_partial_context()
    c.load_cert_chain(cert_path, keyfile=key_path)
    return c


def make_sni_context(config: "Config"):
    def sni_callback(sock, host, _original_ctx):
        for host_cfg in config.hosts:
            if host_cfg.host == host:
                break
        else:
            return ssl.ALERT_DESCRIPTION_HANDSHAKE_FAILURE

        try:
            sock.context = host_cfg.tls.get_ssl_context()
        except Exception:
            log.warn(f"When setting context after SNI; {traceback.format_exc()}")

    c = make_partial_context()
    c.sni_callback = sni_callback
    return c


def update_certificate(
    cert_path: str, key_path: str, hosts: List[str]
) -> datetime.datetime:
    # Check to make sure we actually need to update the certificate
    if os.path.exists(cert_path):
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())

        if cert.not_valid_after > datetime.datetime.now():
            log.info("Certificate exists and is unexpired; skipping regeneration.")
            return cert.not_valid_after

        else:
            log.info("Certificate expired; regenerating.")

    else:
        log.info("Certificate does not exist yet, generating one now.")

    # Preserve the private key if it exists
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)

    else:
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )

        with open(key_path, "wb") as f:
            f.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

    # Generate a self-signed certificate
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hosts[0])])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(host) for host in hosts]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    log.info("Success! Certificate generated and saved.")
    return cert.not_valid_after

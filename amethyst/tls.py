import datetime
import os.path
import logging
import ssl

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from typing import List

log = logging.getLogger("amethyst.tls")


def make_context(cert_path: str, key_path: str):
    c = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    c.options |= (ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)
    c.options |= (ssl.OP_SINGLE_DH_USE | ssl.OP_SINGLE_ECDH_USE)

    c.load_cert_chain(cert_path, keyfile=key_path)
    c.check_hostname = False
    c.verify_mode = ssl.VerifyMode.CERT_OPTIONAL

    return c


def update_certificate(cert_path: str, key_path: str, hosts: List[str]):
    if os.path.exists(cert_path):
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())

        if cert.not_valid_after > (datetime.datetime.now() - datetime.timedelta(days=1)):
            log.info("Certificate exists and won't expire soon, skipping regeneration.")
            return

        else:
            log.info("Certificate expires soon, regenerating.")

    else:
        log.info("Certificate does not exist yet, generating one now.")

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hosts[0])
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow() - datetime.timedelta(days=1)
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=30)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(host) for host in hosts
        ]),
        critical=False
    ).sign(key, hashes.SHA256())

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    log.info("Success! Certificate generated and saved.")

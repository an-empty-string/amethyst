import ssl


def make_context(cert_path: str, key_path: str):
    c = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    c.options |= (ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)
    c.options |= (ssl.OP_SINGLE_DH_USE | ssl.OP_SINGLE_ECDH_USE)

    c.load_cert_chain(cert_path, keyfile=key_path)
    c.check_hostname = False
    c.verify_mode = ssl.VerifyMode.CERT_OPTIONAL

    return c

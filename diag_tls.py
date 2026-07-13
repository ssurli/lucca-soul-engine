import ssl, socket
host = "06c6c795.databases.neo4j.io"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
with socket.create_connection((host, 7687), timeout=10) as s:
    with ctx.wrap_socket(s, server_hostname=host) as ss:
        c = ss.getpeercert(binary_form=False)
        d = ss.getpeercert(True)
        print("TLS:", ss.version())
        import ssl as _s
        dec = _s._ssl._test_decode_cert if hasattr(_s, "_ssl") else None
        print("cert (raw len):", len(d))
        try:
            import OpenSSL  # opzionale
        except ImportError:
            pass
        print("peercert:", c)

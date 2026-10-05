"""TCP relay: 127.0.0.1:17844 -> edge IP:7844 via the sandbox egress proxy (CONNECT).
Lets cloudflared reach the Cloudflare edge without touching the broken local DNS
or direct-TCP path. Proxy credentials are read from the environment, never logged.
"""
import base64
import os
import socket
import threading
import urllib.parse

LISTEN = ("127.0.0.1", 17844)
TARGET_HOST = "198.41.192.37"
TARGET_PORT = 7844

proxy_url = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY", "")
pu = urllib.parse.urlparse(proxy_url)
proxy_host, proxy_port = pu.hostname, pu.port or 3128
auth = base64.b64encode(f"{pu.username}:{pu.password}".encode()).decode()


def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(client):
    try:
        up = socket.create_connection((proxy_host, proxy_port), timeout=15)
        req = (
            f"CONNECT {TARGET_HOST}:{TARGET_PORT} HTTP/1.1\r\n"
            f"Host: {TARGET_HOST}:{TARGET_PORT}\r\n"
            f"Proxy-Authorization: Basic {auth}\r\n\r\n"
        )
        up.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = up.recv(4096)
            if not chunk:
                raise OSError("proxy closed during CONNECT")
            resp += chunk
        if b" 200 " not in resp.split(b"\r\n", 1)[0]:
            raise OSError(f"proxy CONNECT failed: {resp[:80]!r}")
        t1 = threading.Thread(target=pipe, args=(client, up), daemon=True)
        t2 = threading.Thread(target=pipe, args=(up, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except OSError:
        pass
    finally:
        client.close()


srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(LISTEN)
srv.listen(64)
print("relay listening on 127.0.0.1:17844", flush=True)
while True:
    c, _ = srv.accept()
    threading.Thread(target=handle, args=(c,), daemon=True).start()

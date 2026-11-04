#!/usr/bin/env python3
"""Fake internet for the Burner sandbox.

Every TCP connection and UDP packet leaving the sandbox bridge is DNAT-ed here
(see setup.sh). We answer DNS with unique fake IPs, terminate TLS with certs
minted by our own CA, accept HTTP uploads, record everything, and send nothing
anywhere real.

  fakenet.py --make-ca DIR              create CA (ca.pem / ca.key)
  fakenet.py --ca DIR --out OUTDIR      run (TCP 10.77.0.1:9999, DNS 10.77.0.1:5353)
"""
import argparse
import datetime
import ipaddress
import json
import os
import socket
import socketserver
import ssl
import struct
import tempfile
import threading
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

BIND = "10.77.0.1"
SO_ORIGINAL_DST = 80
MAX_BODY = 50 * 1024 * 1024

# ---------------------------------------------------------------- CA / certs

def make_ca(d):
    os.makedirs(d, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Global Trust Root CA")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=365))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    with open(os.path.join(d, "ca.key"), "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    with open(os.path.join(d, "ca.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


class CertMint:
    def __init__(self, ca_dir):
        with open(os.path.join(ca_dir, "ca.key"), "rb") as f:
            self.ca_key = serialization.load_pem_private_key(f.read(), None)
        with open(os.path.join(ca_dir, "ca.pem"), "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read())
        self.cache = {}
        self.lock = threading.Lock()
        self.tmp = tempfile.mkdtemp(prefix="fakenet-certs-")

    def context(self, name):
        name = (name or "localhost").lower()
        with self.lock:
            if name in self.cache:
                return self.cache[name]
            key = ec.generate_private_key(ec.SECP256R1())
            try:
                san = x509.IPAddress(ipaddress.ip_address(name))
            except ValueError:
                san = x509.DNSName(name)
            now = datetime.datetime.now(datetime.timezone.utc)
            cert = (x509.CertificateBuilder()
                    .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name[:64])]))
                    .issuer_name(self.ca_cert.subject).public_key(key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now - datetime.timedelta(days=365))
                    .not_valid_after(now + datetime.timedelta(days=730))
                    .add_extension(x509.SubjectAlternativeName([san]), critical=False)
                    .sign(self.ca_key, hashes.SHA256()))
            path = os.path.join(self.tmp, f"{len(self.cache)}.pem")
            with open(path, "wb") as f:
                f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
                f.write(cert.public_bytes(serialization.Encoding.PEM))
                f.write(self.ca_cert.public_bytes(serialization.Encoding.PEM))
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(path)
            ctx.set_alpn_protocols(["http/1.1"])
            self.cache[name] = ctx
            return ctx

# ---------------------------------------------------------------- recording

class Recorder:
    def __init__(self, out):
        self.out = out
        os.makedirs(os.path.join(out, "bodies"), exist_ok=True)
        self.lock = threading.Lock()
        self.n = 0
        self.dns = {}       # fake ip -> hostname
        self.next_ip = 1

    def fake_ip_for(self, host):
        with self.lock:
            for ip, h in self.dns.items():
                if h == host:
                    return ip
            ip = f"198.18.{self.next_ip // 250}.{self.next_ip % 250 + 1}"
            self.next_ip += 1
            self.dns[ip] = host
            return ip

    def event(self, ev, body=None):
        with self.lock:
            self.n += 1
            ev["id"] = self.n
            ev["t"] = round(time.time(), 3)
            if body:
                fn = f"{self.n}.bin"
                with open(os.path.join(self.out, "bodies", fn), "wb") as f:
                    f.write(body)
                ev["body_file"] = fn
                ev["body_len"] = len(body)
            with open(os.path.join(self.out, "net.jsonl"), "a") as f:
                f.write(json.dumps(ev) + "\n")

# ---------------------------------------------------------------- DNS

def dns_server(rec):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((BIND, 5353))
    while True:
        data, addr = s.recvfrom(4096)
        try:
            tid, flags, qd = struct.unpack(">HHH", data[:6])
            i, labels = 12, []
            while data[i]:
                labels.append(data[i + 1:i + 1 + data[i]].decode(errors="replace"))
                i += data[i] + 1
            qname = ".".join(labels).lower()
            qtype = struct.unpack(">H", data[i + 1:i + 3])[0]
            question = data[12:i + 5]
            rec.event({"type": "dns", "qname": qname, "qtype": qtype, "src": addr[0]})
            if qtype == 1:   # A
                ip = rec.fake_ip_for(qname)
                ans = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + socket.inet_aton(ip)
                resp = struct.pack(">HHHHHH", tid, 0x8180, 1, 1, 0, 0) + question + ans
            else:            # no AAAA etc: force IPv4
                resp = struct.pack(">HHHHHH", tid, 0x8180, 1, 0, 0, 0) + question
            s.sendto(resp, addr)
        except Exception as e:  # malformed / non-DNS UDP
            rec.event({"type": "udp", "src": addr[0], "len": len(data), "error": str(e)[:80]}, data[:4096])

# ---------------------------------------------------------------- TCP

def recv_until(sock, marker, limit=65536):
    """Read until `marker`, EOF or a quiet socket. A raw (non-HTTP) client often sends
    its data and then waits for the server to answer: keep what it sent."""
    buf = b""
    try:
        while marker not in buf and len(buf) < limit:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
    except socket.timeout:
        if not buf:
            raise
    return buf


def read_http(sock, first):
    head, _, rest = first.partition(b"\r\n\r\n")
    lines = head.decode(errors="replace").split("\r\n")
    method, _, rest_line = lines[0].partition(" ")
    path = rest_line.rsplit(" ", 1)[0]
    headers = {}
    for ln in lines[1:]:
        k, _, v = ln.partition(":")
        headers[k.strip().lower()] = v.strip()
    body = rest
    if "content-length" in headers:
        n = min(int(headers["content-length"] or 0), MAX_BODY)
        while len(body) < n:
            chunk = sock.recv(65536)
            if not chunk:
                break
            body += chunk
    elif "chunked" in headers.get("transfer-encoding", ""):
        raw = body
        while not raw.endswith(b"0\r\n\r\n") and len(raw) < MAX_BODY:
            chunk = sock.recv(65536)
            if not chunk:
                break
            raw += chunk
        body, i = b"", 0
        while i < len(raw):
            j = raw.find(b"\r\n", i)
            if j < 0:
                break
            size = int(raw[i:j].split(b";")[0] or b"0", 16)
            if size == 0:
                break
            body += raw[j + 2:j + 2 + size]
            i = j + 2 + size + 2
    return method, path, headers, body


HTTP_METHODS = (b"GET ", b"POST", b"PUT ", b"HEAD", b"PATC", b"DELE", b"OPTI", b"CONN")


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        rec, mint = self.server.rec, self.server.mint
        sock = self.request
        try:
            raw = sock.getsockopt(socket.SOL_IP, SO_ORIGINAL_DST, 16)
            dport = struct.unpack(">H", raw[2:4])[0]
            dip = socket.inet_ntoa(raw[4:8])
        except OSError:
            dip, dport = "?", 0
        host = rec.dns.get(dip)
        ev = {"type": "tcp", "dst_ip": dip, "dst_port": dport, "host": host, "src": self.client_address[0]}
        sock.settimeout(5)
        try:
            peek = sock.recv(8, socket.MSG_PEEK)
        except socket.timeout:
            ev["proto"] = "silent"
            rec.event(ev)
            return
        if not peek:
            ev["proto"] = "empty"
            rec.event(ev)
            return
        if peek[0] == 0x16:  # TLS ClientHello
            sni = {}

            def cb(sslobj, servername, ctx):
                sni["name"] = servername
                if servername:
                    sslobj.context = mint.context(servername)

            base = mint.context(host or dip)
            base.sni_callback = cb
            try:
                sock = base.wrap_socket(sock, server_side=True)
                ev["tls"] = True
                ev["sni"] = sni.get("name")
            except ssl.SSLError as e:
                ev["proto"] = "tls-rejected"   # client pinned / did not trust our CA
                ev["sni"] = sni.get("name")
                ev["error"] = str(e)[:120]
                rec.event(ev)
                return
        try:
            first = recv_until(sock, b"\r\n\r\n")
            if first[:4] in HTTP_METHODS:
                method, path, headers, body = read_http(sock, first)
                ev.update({"proto": "https" if ev.get("tls") else "http", "method": method, "path": path,
                           "http_host": headers.get("host"), "user_agent": headers.get("user-agent"),
                           "content_type": headers.get("content-type")})
                rec.event(ev, body or None)
                resp = b"{}"
                sock.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                             + str(len(resp)).encode() + b"\r\nConnection: close\r\n\r\n" + resp)
            else:
                data = first
                sock.settimeout(3)
                try:
                    while len(data) < MAX_BODY:
                        chunk = sock.recv(65536)
                        if not chunk:
                            break
                        data += chunk
                except socket.timeout:
                    pass
                ev["proto"] = "raw-tls" if ev.get("tls") else "raw"
                rec.event(ev, data or None)
        except (socket.timeout, ConnectionError, ssl.SSLError) as e:
            ev.setdefault("proto", "error")
            ev["error"] = str(e)[:120]
            rec.event(ev)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-ca")
    ap.add_argument("--ca", default="/opt/burner")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.make_ca:
        make_ca(a.make_ca)
        return
    rec = Recorder(a.out)
    threading.Thread(target=dns_server, args=(rec,), daemon=True).start()
    srv = Server((BIND, 9999), Handler)
    srv.rec, srv.mint = rec, CertMint(a.ca)
    print("fakenet listening", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()

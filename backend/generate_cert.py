"""Genera un certificato TLS auto-firmato per l'uso in LAN (non per esposizione
su internet — un browser mostrera' sempre un avviso "non attendibile" perche'
nessuna Certification Authority pubblica lo ha firmato: la connessione resta
comunque cifrata, il che basta per una rete interna fidata).

Per esposizione pubblica serve un certificato firmato da una CA reale (es.
Let's Encrypt) — vedi docs/guida-installazione-e-test.md, sezione HTTPS pubblico.

Uso: python generate_cert.py <cert.pem> <key.pem> <hostname> [ip...]
"""

from __future__ import annotations

import datetime
import ipaddress
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def main() -> None:
    if len(sys.argv) < 4:
        print("Uso: python generate_cert.py <cert.pem> <key.pem> <hostname> [ip...]", file=sys.stderr)
        raise SystemExit(1)

    cert_path, key_path, hostname, *extra_ips = sys.argv[1:]

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])

    san_names: list[x509.GeneralName] = [x509.DNSName(hostname), x509.DNSName("localhost")]
    san_ips = [ipaddress.ip_address("127.0.0.1")]
    for ip_str in extra_ips:
        try:
            san_ips.append(ipaddress.ip_address(ip_str))
        except ValueError:
            san_names.append(x509.DNSName(ip_str))  # non era un IP, trattato come hostname aggiuntivo
    san_names.extend(x509.IPAddress(ip) for ip in san_ips)

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))  # ~2 anni, sotto il limite accettato dai browser per i self-signed
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Certificato scritto in {cert_path}, chiave in {key_path}")
    print(f"Valido per: {hostname}, localhost, 127.0.0.1" + (f", {', '.join(extra_ips)}" if extra_ips else ""))


if __name__ == "__main__":
    main()

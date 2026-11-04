# The "candidate's laptop": a normal-looking developer machine.
FROM node:22-bookworm

RUN apt-get update -q && apt-get install -y -q --no-install-recommends \
      python3 python3-pip python3-venv git curl wget ca-certificates faketime procps \
    && rm -rf /var/lib/apt/lists/*

# Trust the fake internet's CA so HTTPS exfiltration is readable.
COPY burner-ca.crt /usr/local/share/ca-certificates/burner-ca.crt
RUN update-ca-certificates
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/burner-ca.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt

# node image ships user "node" (uid 1000); rename it to look like a real dev.
RUN usermod -l dev -d /home/dev -m node && groupmod -n dev node
USER dev
WORKDIR /home/dev

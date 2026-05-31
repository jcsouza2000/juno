#!/bin/bash
# Gerar certificado SSL auto-assinado para desenvolvimento

SSL_DIR="$(dirname "$0")/ssl"
mkdir -p "$SSL_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$SSL_DIR/key.pem" \
    -out "$SSL_DIR/cert.pem" \
    -subj "/C=BR/ST=SP/L=Sao Paulo/O=JUNO AI/OU=Dev/CN=*.juno.local" \
    -addext "subjectAltName=DNS:api.juno.local,DNS:app.juno.local,DNS:localhost,IP:127.0.0.1"

echo "Certificado SSL gerado em: $SSL_DIR"

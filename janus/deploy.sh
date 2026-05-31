#!/bin/bash
# JUNO Deploy Local Script

ENV=${1:-staging}

echo "JUNO Deploy - Ambiente: $ENV"

if [ ! -f .env ]; then
    echo ".env nao encontrado. Copiando de .env.example..."
    cp .env.example .env
fi

if [ ! -f infra/nginx/ssl/cert.pem ]; then
    echo "Gerando certificado SSL auto-assinado..."
    bash infra/nginx/generate-ssl.sh
fi

if [ "$ENV" = "production" ]; then
    echo "Iniciando producao..."
    docker compose --profile production up -d --build
else
    echo "Iniciando staging..."
    docker compose up -d --build
fi

sleep 30

echo "Health checks..."
curl -sf http://localhost:8000/api/v1/health && echo "Backend OK" || echo "Backend FAIL"
curl -sf http://localhost:8080 && echo "Frontend OK" || echo "Frontend FAIL"

echo ""
echo "Dashboards disponiveis:"
echo "   App:        http://localhost:8080"
echo "   API:        http://localhost:8000/api/v1/docs"
echo "   Grafana:    http://localhost:3000 (admin/admin)"
echo "   Prometheus: http://localhost:9090"

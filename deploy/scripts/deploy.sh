#!/bin/bash
# JUNO Deploy Script
# Uso: ./deploy.sh [environment]

ENV=${1:-staging}
COMPOSE_FILE="docker-compose.prod.yml"

echo "🚀 Deploying JUNO to $ENV environment..."

# Load environment variables
if [ -f ".env.$ENV" ]; then
    export $(cat .env.$ENV | xargs)
    echo "✅ Environment loaded: .env.$ENV"
else
    echo "❌ Environment file not found: .env.$ENV"
    exit 1
fi

# Pull latest images (if using registry)
# docker-compose -f $COMPOSE_FILE pull

# Build and start
docker-compose -f $COMPOSE_FILE down
docker-compose -f $COMPOSE_FILE up -d --build

# Wait for health checks
echo "⏳ Waiting for services to be healthy..."
sleep 30

# Check health
if curl -f http://localhost:9050/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend health check failed"
    exit 1
fi

# Run migrations
echo "🔄 Running database migrations..."
docker-compose -f $COMPOSE_FILE exec -T backend alembic upgrade head

# Seed if needed (only in staging)
if [ "$ENV" == "staging" ]; then
    echo "🌱 Seeding database..."
    docker-compose -f $COMPOSE_FILE exec -T backend python -m app.seed
fi

echo "🎉 Deploy completed successfully!"
echo "   Backend: http://localhost:9050"
echo "   Frontend: http://localhost:4000"
echo "   Kong Admin: http://localhost:8001"

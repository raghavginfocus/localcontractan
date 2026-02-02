#!/bin/bash
# Start all required services for Contract Knowledge Graph system

set -e

echo "🚀 Starting Contract Knowledge Graph Services"
echo "=============================================="
echo ""

# Detect container runtime (Docker or Podman)
COMPOSE_CMD=""
if command -v podman-compose > /dev/null 2>&1 && podman info > /dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
    echo "✅ Using Podman Compose"
elif command -v docker-compose > /dev/null 2>&1 && docker info > /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    echo "✅ Using Docker Compose"
elif command -v docker > /dev/null 2>&1 && docker info > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    echo "✅ Using Docker Compose (v2)"
else
    echo "❌ No container runtime found!"
    echo "   Please ensure Docker or Podman is installed and running."
    exit 1
fi

# Navigate to docker directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/docker"

echo "📦 Starting services with $COMPOSE_CMD..."
echo ""

# Start all services
$COMPOSE_CMD up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

echo ""
echo "🔍 Checking service status..."
$COMPOSE_CMD ps

echo ""
echo "✅ Services started!"
echo ""
echo "📋 Service URLs:"
echo "   • Fuseki:     http://localhost:3030"
echo "   • Milvus:     http://localhost:19530"
echo "   • MinIO:      http://localhost:9001"
echo "   • Attu (UI):  http://localhost:8080"
echo "   • Ollama:     http://localhost:11434"
echo ""
echo "🧪 To verify services are healthy, run:"
echo "   cd agents && PYTHONPATH=src uv run python ../scripts/health_check.py"
echo ""

#!/bin/bash
# Script para ver los logs del contenedor backend de Docker
# Usage: ./log_backend.sh

CONTAINER_NAME="backend"

if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ El contenedor '$CONTAINER_NAME' no está corriendo"
    docker ps -a --filter "name=vocab" --format "table {{.Names}}\t{{.Status}}"
    exit 1
fi

echo "📋 Mostrando logs de '$CONTAINER_NAME'..."
echo "Presiona Ctrl+C para salir"
echo ""

docker logs -f "$CONTAINER_NAME"

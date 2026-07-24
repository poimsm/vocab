#!/bin/bash

# Script para reapertura de batches antiguos (Memoria espaciada)
# Ejecutar manualmente: bash bin/reopen-batches.sh
# O configurar en cron: 0 2 * * * cd /ruta/del/proyecto && bash bin/reopen-batches.sh

set -e

BACKEND_CONTAINER="fastapi_container"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

echo_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Verificar si el contenedor está corriendo
if ! docker ps --filter "name=$BACKEND_CONTAINER" --filter "status=running" | grep -q "$BACKEND_CONTAINER"; then
    echo_error "El contenedor '$BACKEND_CONTAINER' no está corriendo"
    echo "Inicia los servicios con: docker-compose up -d"
    exit 1
fi

echo_status "Ejecutando reapertura de batches antiguos..."
echo ""

# Ejecutar el script Python en el contenedor
docker exec -i "$BACKEND_CONTAINER" sh -c "export PYTHONPATH=\$PYTHONPATH:/app && python /app/scripts/reopen_old_batches.py"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo_status "Reapertura completada exitosamente"
else
    echo ""
    echo_error "Error durante la reapertura"
    exit 1
fi

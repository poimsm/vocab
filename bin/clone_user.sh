#!/bin/bash

CLEAN_FLAG=""

# Verificar si se pasó --clean
if [ "$3" = "--clean" ]; then
    CLEAN_FLAG=" --clean"
fi

if [ $# -lt 2 ]; then
    echo "❌ Uso: $0 <SOURCE_USER_ID> <TARGET_USER_ID> [--clean]"
    echo ""
    echo "Ejemplos:"
    echo "  $0 5 10              # Clonar usuario 5 a 10"
    echo "  $0 5 10 --clean      # Clonar usuario 5 a 10 (limpiar 10 primero)"
    exit 1
fi

SOURCE_USER_ID=$1
TARGET_USER_ID=$2

if [ -n "$CLEAN_FLAG" ]; then
    echo "Clonando usuario ID=$SOURCE_USER_ID a usuario ID=$TARGET_USER_ID (limpiando primero)..."
else
    echo "Clonando usuario ID=$SOURCE_USER_ID a usuario ID=$TARGET_USER_ID..."
fi

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && cd /app && python manage.py clone-user $SOURCE_USER_ID $TARGET_USER_ID$CLEAN_FLAG"

echo "Fin."

#!/bin/bash

if [ $# -lt 2 ]; then
    echo "❌ Uso: $0 <SOURCE_USER_ID> <TARGET_USER_ID>"
    echo ""
    echo "Ejemplo:"
    echo "  $0 5 10              # Clonar usuario 5 a 10 (limpiando primero)"
    exit 1
fi

SOURCE_USER_ID=$1
TARGET_USER_ID=$2

echo "Clonando usuario ID=$SOURCE_USER_ID a usuario ID=$TARGET_USER_ID (limpiando primero)..."

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && cd /app && python manage.py clone-user $SOURCE_USER_ID $TARGET_USER_ID"

echo "Fin."

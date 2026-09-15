#!/bin/bash

if [ $# -ne 1 ]; then
    echo "❌ Uso: $0 <USER_ID>"
    echo ""
    echo "Ejemplo:"
    echo "  $0 5"
    exit 1
fi

USER_ID=$1

echo "Cargando configuración de usuario ID=$USER_ID..."

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && cd /app && python manage.py load-user-configuration $USER_ID"

echo "✅ Configuración de usuario cargada."

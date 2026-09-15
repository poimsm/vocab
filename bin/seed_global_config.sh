#!/bin/bash

echo "Cargando configuración global..."

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && cd /app && python manage.py load-global-config"

echo "✅ Configuración global cargada."

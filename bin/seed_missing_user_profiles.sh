#!/bin/bash

echo "Creando perfiles para usuarios sin perfil..."

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && cd /app && python manage.py seed-missing-user-profiles"

echo "✅ Perfiles faltantes creados."

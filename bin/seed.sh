#!/bin/bash

echo "Iniciando proceso de sembrado..."

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && cd /app && python manage.py load-global-config"
docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && python /app/seeds/seed_users.py"

echo "Fin proceso."
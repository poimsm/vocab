#!/bin/bash

echo "Iniciando proceso de sembrado..."

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && python /app/seeds/seed_config.py"
docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && python /app/seeds/seed_users.py"

echo "Fin proceso."
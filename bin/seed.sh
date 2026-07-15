#!/bin/bash

echo "Iniciando proceso de sembrado..."

docker exec -i fastapi_container sh -c "export PYTHONPATH=\$PYTHONPATH:/app && python /app/seed_config.py"

echo "Fin proceso."
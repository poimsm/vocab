#!/bin/bash

# Detener el script si ocurre algun error
set -e

# Asegurarse de que los contenedores esten corriendo
if [ -z "$(docker ps -q -f name=fastapi_container)" ]; then
    echo "⚠️  El contenedor 'fastapi_container' no esta corriendo."
    echo "🚀 Iniciando servicios con docker-compose..."
    docker compose up -d
    # Esperar un par de segundos a que levante
    sleep 3
fi

echo "--------------------------------------------------"
echo "   Gestor de Migraciones Alembic (SQLModel)       "
echo "--------------------------------------------------"
echo "1) Generar nueva migracion automatica (revision)"
echo "2) Aplicar migraciones pendientes (upgrade head)"
echo "3) Ver historial de versiones (history)"
echo "4) Revertir ultima migracion (downgrade -1)"
echo "5) Salir"
echo "--------------------------------------------------"
read -p "Selecciona una opcion [1-5]: " opcion

case $opcion in
    1)
        read -p "Introduce el mensaje para la migracion (ej: add_type_to_example): " message
        if [ -z "$message" ]; then
            echo "❌ El mensaje no puede estar vacio."
            exit 1
        fi
        echo "⏳ Generando revision automatica..."
        # Corre alembic dentro del contenedor de FastAPI
        docker compose exec backend alembic revision --autogenerate -m "$message"
        echo "✅ ¡Migracion generada con exito en la carpeta de alembic!"
        ;;
    2)
        echo "⏳ Aplicando migraciones en la base de datos..."
        docker compose exec backend alembic upgrade head
        echo "✅ ¡Base de datos actualizada!"
        ;;
    3)
        echo "📋 Historial de migraciones:"
        docker compose exec backend alembic history --verbose
        ;;
    4)
        echo "⏳ Revirtiendo la ultima migracion..."
        docker compose exec backend alembic downgrade -1
        echo "⏪ Hecho."
        ;;
    5)
        echo "👋 Saliendo."
        exit 0
        ;;
    *)
        echo "❌ Opcion no valida."
        exit 1
        ;;
esac
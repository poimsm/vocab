#!/bin/bash

# Detener el script si ocurre algún error
set -e

# Asegurarse de que los contenedores estén corriendo
if [ -z "$(docker ps -q -f name=fastapi_container)" ]; then
    echo "⚠️  El contenedor 'fastapi_container' no está corriendo."
    echo "🚀 Iniciando servicios con docker-compose..."
    docker compose up -d
    # Esperar un par de segundos a que levante
    sleep 3
fi

echo "--------------------------------------------------"
echo "   Gestor de Migraciones Alembic (SQLModel)       "
echo "--------------------------------------------------"
echo "1) Generar nueva migración automática (revision)"
echo "2) Aplicar migraciones pendientes (upgrade head)"
echo "3) Ver historial de versiones (history)"
echo "4) Revertir última migración (downgrade -1)"
echo "5) Salir"
echo "--------------------------------------------------"
read -p "Selecciona una opción [1-5]: " opcion

case $opcion in
    1)
        read -p "Introduce el mensaje para la migración (ej: add_type_to_example): " message
        if [ -z "$message" ]; then
            echo "❌ El mensaje no puede estar vacío."
            exit 1
        fi
        echo "⏳ Generando revisión automática..."
        # Corre alembic dentro del contenedor de FastAPI
        docker compose exec backend alembic revision --autogenerate -m "$message"
        echo "✅ ¡Migración generada con éxito en la carpeta de alembic!"
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
        echo "⏳ Revirtiendo la última migración..."
        docker compose exec backend alembic downgrade -1
        echo "⏪ Hecho."
        ;;
    5)
        echo "👋 Saliendo."
        exit 0
        ;;
    *)
        echo "❌ Opción no válida."
        exit 1
        ;;
esac
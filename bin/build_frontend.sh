#!/bin/bash

# Detener el script si ocurre algún error
set -e

# Obtener la ruta absoluta de la raíz del proyecto de forma compatible con Linux/Mac/Windows
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/.."

# Detectar la ruta según el sistema operativo
if command -v cygpath >/dev/null 2>&1; then
    ROOT_DIR=$(pwd -W) # Windows (Git Bash)
else
    ROOT_DIR=$(pwd)    # Linux nativo / macOS
fi

# Importar tu script de comandos compartidos si existe
if [ -f "$DIR/commands.sh" ]; then
    source "$DIR/commands.sh"
fi

echo "🚀 Iniciando build efímero del Frontend con Node 20..."

# Asignar un valor por defecto si la variable no viene del entorno o de un .env
VITE_API_BASE_VALUE="${VITE_API_BASE}"
if [ -z "$VITE_API_BASE_VALUE" ]; then
    VITE_API_BASE_VALUE="/api"
fi

# Desactivar la conversión de rutas SOLO si estamos en Windows
case "$(uname -s)" in
    CYGWIN*|MSYS*|MINGW*)
        export MSYS_NO_PATHCONV=1
        ;;
esac

# 1. Instalar dependencias
echo "📦 Instalando dependencias..."
docker run --rm \
  -v "${ROOT_DIR}/frontend:/app" \
  -w /app \
  node:20-alpine \
  npm install

# 2. Compilar producción
echo "🏗️  Compilando el proyecto..."
docker run --rm \
  -v "${ROOT_DIR}/frontend:/app" \
  -w /app \
  -e VITE_API_BASE="$VITE_API_BASE_VALUE" \
  node:20-alpine \
  npm run build

echo "✨ ¡Build completado con éxito! Los archivos estáticos están en ./frontend/dist"
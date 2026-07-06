#!/bin/bash

# Detener el script si ocurre algún error
set -e

# Obtener la ruta raíz del proyecto
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/.."

# 🔥 MAGIA PARA WINDOWS: Captura la ruta absoluta real estilo Windows (C:/...)
if command -v cygpath >/dev/null 2>&1; then
    # Si estamos en Git Bash/MSYS, usamos la ruta nativa de Windows
    ROOT_DIR=$(pwd -W)
else
    ROOT_DIR=$(pwd)
fi

# Importar tu script de comandos compartidos si existe
if [ -f "$DIR/commands.sh" ]; then
    source "$DIR/commands.sh"
fi

echo "🚀 Iniciando build efímero del Frontend con Node 20..."

# Leer la variable VITE_API_BASE desde tu archivo .env local si existe
if [ -f "$ROOT_DIR/.env" ]; then
    export $(grep -v '^#' "$ROOT_DIR/.env" | xargs)
fi

# Forzar a Git Bash a no tocar las rutas internas de Docker (/app)
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
  -e VITE_API_BASE="${VITE_API_BASE:-/api}" \
  node:20-alpine \
  npm run build

echo "✨ ¡Build completado con éxito! Los archivos estáticos están en ./frontend/dist"
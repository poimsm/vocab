#!/bin/bash

source ./bin/validar_entorno.sh "$1"
source ./bin/confirm_prod.sh "$1"

source ./bin/commands.sh

CMD_PREFIX=$(detectar_os)

echo "Destruyendo server..."
${CMD_PREFIX} docker-compose -f docker-compose.base.yml -f docker-compose.$1.yml down -v --rmi all
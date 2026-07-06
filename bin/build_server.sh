#!/bin/bash

source ./bin/validar_entorno.sh "$1"
source ./bin/commands.sh

CMD_PREFIX=$(detectar_os)

${CMD_PREFIX} docker-compose -f docker-compose.base.yml -f docker-compose.$1.yml up -d --build

echo 'Server up'
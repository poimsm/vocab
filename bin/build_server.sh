#!/bin/bash

source ./bin/validate_env.sh "$1"
source ./bin/commands.sh

CMD_PREFIX=$(detectar_os)

${CMD_PREFIX} docker compose up -d --build

echo 'Server up'
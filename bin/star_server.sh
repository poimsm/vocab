#!/bin/bash

# source ./bin/validate_env.sh "$1"
# source ./bin/confirm_prod.sh "$1"

source ./bin/commands.sh

CMD_PREFIX=$(detectar_os)

echo
echo "Starting server..."
${CMD_PREFIX} docker compose start
echo
echo 'Server up'

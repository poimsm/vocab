#!/bin/bash

source ./bin/commands.sh

CMD_PREFIX=$(detectar_os)

echo
echo "Stopping and removing containers..."
${CMD_PREFIX} docker compose down
echo
echo "Building and starting fresh containers..."
${CMD_PREFIX} docker compose up -d
echo 'Server up with fresh containers'

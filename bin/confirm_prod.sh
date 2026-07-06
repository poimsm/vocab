#!/bin/bash

# Pide confirmación para continuar en producción
if [ "$1" = "prod" ]; then
    read -p "Estás en producción, ¿deseas continuar con la operación? (y/n): " confirmacion
    if [[ ! $confirmacion =~ ^[Yy]$ ]]; then
        echo "Operación cancelada."
        exit 1  # Sale con un código de error si la respuesta no es afirmativa
    fi
fi
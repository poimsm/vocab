#!/bin/bash

# Función para imprimir en rojo
print_error() {
    echo -e "\e[31mERROR: $1\e[0m"
}

# Verificación del parámetro
if [ -z "$1" ]; then
    print_error "Falta el entorno de despliegue como argumento."
    echo "Uso correcto: $0 <entorno>"
    echo "Donde <entorno> debe ser 'dev' para desarrollo o 'prod' para produccion."
    exit 1
fi

if [ "$1" != "dev" ] && [ "$1" != "prod" ]; then
    print_error "Argumento invalido: '$1'."
    echo "Uso correcto: $0 <entorno>"
    echo "Donde <entorno> debe ser 'dev' para desarrollo o 'prod' para produccion."
    exit 1
fi
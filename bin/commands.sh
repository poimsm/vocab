#!/bin/bash

# Funcion para detectar el SO y devolver 'winpty' o cadena vacia
detectar_os() {
    case "$(uname -s)" in
        CYGWIN*|MSYS*|MINGW*)
            echo 'winpty'
            ;;
        *)
            echo ''
            ;;
    esac
}


get_docker_compose() {
    case "$(uname -s)" in
        CYGWIN*|MSYS*|MINGW*)
            echo 'docker-compose'
            ;;
        *)
            echo '/usr/local/bin/docker-compose'
            ;;
    esac
}
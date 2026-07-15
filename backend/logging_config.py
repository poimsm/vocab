# backend/logging_config.py
import logging
import sys

def setup_logger():
    # 1. Definir el formato de los logs (puedes meterle colores o timestamps)
    log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 2. Configurar el logger raíz
    logging.basicConfig(
        level=logging.INFO,  # Cambia a logging.DEBUG si quieres ver TODO
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)  # Esto manda los logs a la consola para Docker
        ]
    )

    # 3. Silenciar un poco los logs ultra-verbosos de librerías terceras si es necesario
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger("vocab_app")
    return logger

# Inicializamos el logger para importarlo donde queramos
logger = setup_logger()
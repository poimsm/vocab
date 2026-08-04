# backend/logging_config.py
import logging
import sys
from pathlib import Path

def setup_logger():
    # 1. Definir el formato de los logs (puedes meterle colores o timestamps)
    log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 2. Crear la carpeta de logs si no existe
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    # 3. Configurar handlers
    handlers = [
        logging.StreamHandler(sys.stdout),  # Consola
        logging.FileHandler(log_file, encoding="utf-8")  # Archivo
    ]

    # 4. Configurar el logger raíz
    logging.basicConfig(
        level=logging.INFO,  # Cambia a logging.DEBUG si quieres ver TODO
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    # 5. Silenciar un poco los logs ultra-verbosos de librerías terceras si es necesario
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger("vocab_app")
    return logger

# Inicializamos el logger para importarlo donde queramos
logger = setup_logger()
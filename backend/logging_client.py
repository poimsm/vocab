import requests
import os
from typing import Optional
import inspect

LOGGING_SERVICE_URL = os.getenv("LOGGING_SERVICE_URL", "http://logging_service:8000")


class CentralizedLogger:
    """Logger que imita la interfaz de logging.Logger pero envía logs a un servicio centralizado"""

    def __init__(self, service_url: str = LOGGING_SERVICE_URL, default_source: str = "unknown"):
        self.service_url = service_url
        self.default_source = default_source

    def _get_caller_info(self) -> tuple:
        """Detecta automáticamente el archivo:línea que está llamando al logger"""
        try:
            frame = inspect.currentframe()
            # Sube el stack: _get_caller_info -> _send_log -> debug/info/etc -> caller
            caller_frame = frame.f_back.f_back.f_back
            filename = caller_frame.f_code.co_filename
            lineno = caller_frame.f_lineno

            # Obtén solo el nombre del archivo (sin la ruta completa)
            filename = filename.split("/")[-1].split("\\")[-1]

            return filename, lineno
        except Exception:
            return "unknown", 0

    def _send_log(self, level: str, message: str, source: str = None):
        """Envía un log al servicio centralizado"""
        if source is None:
            filename, lineno = self._get_caller_info()
            source = f"{filename}:{lineno}"

        try:
            requests.post(
                f"{self.service_url}/logs",
                json={"level": level, "message": message, "source": source},
                timeout=2,
            )
        except Exception:
            # No fallar la aplicación si el servicio de logging está caído
            pass

    def debug(self, message: str, *args, **kwargs):
        """Log de nivel DEBUG"""
        source = kwargs.pop("source", None)
        if args:
            message = message % args
        self._send_log("DEBUG", message, source)

    def info(self, message: str, *args, **kwargs):
        """Log de nivel INFO"""
        source = kwargs.pop("source", None)
        if args:
            message = message % args
        self._send_log("INFO", message, source)

    def warning(self, message: str, *args, **kwargs):
        """Log de nivel WARNING"""
        source = kwargs.pop("source", None)
        if args:
            message = message % args
        self._send_log("WARNING", message, source)

    def warn(self, message: str, *args, **kwargs):
        """Alias para warning()"""
        self.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        """Log de nivel ERROR"""
        source = kwargs.pop("source", None)
        if args:
            message = message % args
        self._send_log("ERROR", message, source)

    def critical(self, message: str, *args, **kwargs):
        """Log de nivel CRITICAL"""
        source = kwargs.pop("source", None)
        if args:
            message = message % args
        self._send_log("CRITICAL", message, source)

    def fatal(self, message: str, *args, **kwargs):
        """Alias para critical()"""
        self.critical(message, *args, **kwargs)


# Instancia global del logger
logger = CentralizedLogger()

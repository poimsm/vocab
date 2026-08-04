import functools
import json
from typing import Any, Callable
from logging_client import logger


def log_endpoint(func: Callable) -> Callable:
    """
    Decorador que registra el nombre del endpoint y su respuesta.

    Uso:
        @router.get("/example")
        @log_endpoint
        def get_example():
            return {"data": "example"}
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Obtener el nombre del endpoint
        endpoint_name = func.__name__
        logger.info(f"[ENDPOINT_START] {endpoint_name}")

        try:
            # Ejecutar la función
            result = func(*args, **kwargs)

            # Loguear la respuesta (truncada si es muy grande)
            try:
                response_str = json.dumps(result, default=str)
                if len(response_str) > 500:
                    response_str = response_str[:500] + "..."
            except:
                response_str = str(result)[:500]

            logger.info(f"[ENDPOINT_END] {endpoint_name} | Response: {response_str}")
            return result
        except Exception as e:
            logger.error(f"[ENDPOINT_ERROR] {endpoint_name} | Error: {str(e)}")
            raise

    return wrapper

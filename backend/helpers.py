from typing import Union, List
from logging_config import logger


class TextFormatter:
    @staticmethod
    def capitalize(data: Union[str, List[str]]) -> Union[str, List[str]]:
        """
        Convierte la primera letra en mayúscula.
        Soporta un único string o una lista de strings.
        """
        if isinstance(data, list):
            # Si es una lista, procesamos cada elemento si es un string válido
            return [s.capitalize() if isinstance(s, str) else s for s in data]

        if isinstance(data, str):
            # Si es un único string
            return data.capitalize()

        # Si pasan un None o un tipo de dato no esperado, lo devuelve tal cual
        return data


def chunk_list(lst, n):
    logger.debug(f"Chunking list of {len(lst)} items with chunk size {n}")
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

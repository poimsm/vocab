
import enum

class ContentSourceType(str, enum.Enum):
    """Fuentes de generación de contenido."""
    LEARNING_PATH = "learning_path"    # Contenido del learning path normal
    BOOST = "boost"                    # Contenido de palabras boosteadas
    CUSTOM = "custom"                  # Contenido generado manualmente


class ContentType(str, enum.Enum):
    EXAMPLE = "example"
    BEST_OPTIONS = "best_options"
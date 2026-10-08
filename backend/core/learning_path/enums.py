import enum


class LearningPathGenerationMonitorStatus(str, enum.Enum):
    """Estados del monitor de generación de contenido del learning path."""
    IDLE = "idle"                # Sin generar
    GENERATING = "generating"    # Generando


class LearningPathGenerationHistoryStatus(str, enum.Enum):
    """Estados del historial de generación de contenido."""
    COMPLETED = "completed"      # Completado exitosamente
    FAILED = "failed"            # Error durante la generación


class LearningState(str, enum.Enum):
    """Estados de aprendizaje de una palabra."""
    NEW = "new"
    LEARNING = "learning"
    REINFORCING = "reinforcing"
    SPACING = "spacing"
    ALMOST_LEARNED = "almost_learned"
    LEARNED = "learned"
    REVIEW = "review"


class LearningPathQueueStatus(str, enum.Enum):
    """Estados de items en la cola de learning path."""
    PENDING = "pending"
    TRANSFERRED = "transferred"
    CONSUMED = "consumed"


class PathAnomalyType(str, enum.Enum):
    """Tipos de anomalías detectadas en el learning path."""
    OVERSIZED_PATH = "oversized_path"  # Path > 20 items
    INACTIVE_WORDS_IN_PATH = "inactive_words_in_path"  # Palabras inactivas en path
    LEARNED_WORDS_IN_PATH = "learned_words_in_path"  # Palabras LEARNED en path
    INFINITE_GENERATION_LOOP = "infinite_generation_loop"  # Generando sin progreso
    EMPTY_QUEUE_WITH_NEW_WORDS = "empty_queue_with_new_words"  # Queue vacía pero hay palabras NEW
    CURSOR_MISALIGNMENT = "cursor_misalignment"  # Cursor fuera de rango
    CORRUPTED_STATISTICS = "corrupted_statistics"  # Estadísticas inconsistentes

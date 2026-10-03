from enum import Enum


class GenerationSourceModule(str, Enum):
    WORDS = "words_module"
    ROLEPLAY = "roleplay_module"
    QUICK_WRITE = "quick_write_module"
    COLLOCATIONS = "collocations_module"
    EXAMPLES = "examples_module"


class GenerationAIRegistryStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    DISCARDED = "DISCARDED"


class GenerationAIStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DISCARDED = "DISCARDED"

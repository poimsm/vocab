from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class SkillDemand:
    skill_type: str  # Ej: "examples", "best_options", "pronunciation"
    quantity: int    # Cuántos ejercicios generar de esta skill
    process_event: str
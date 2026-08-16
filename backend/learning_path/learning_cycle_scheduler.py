"""
DEPRECADO: LearningCycleScheduler

Esta clase ha sido eliminada porque el LearningPath se auto-regula
y no necesita un proceso periódico que monitoree la emergencia de palabras antiguas.

El sistema se encarga naturalmente de:
- Crear nuevos segmentos cuando es necesario (ContentPlanner.ensure_path)
- Administrar look-ahead (LearningPathCursor)
- Registrar exposiciones reales (LearningTracker)

No hay necesidad de un scheduler externo.
"""

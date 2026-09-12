"""
Integration module for path health monitoring and auto-repair.
Use this from content_planner to check and repair path anomalies automatically.
"""

from sqlmodel import Session
from logging_client import logger

from models import ContentType
from learning_path.path_health_monitor import PathHealthMonitor
from learning_path.path_repair_service import PathRepairService


class PathHealthIntegration:
    """
    Integración del sistema de health check y auto-repair.
    Se utiliza desde ContentPlanner.ensure_ready() al inicio.
    """

    @staticmethod
    def check_and_repair(
        session: Session,
        user_id: int,
        content_type: ContentType,
    ) -> bool:
        """
        Chequea la salud del path y auto-repara anomalías.

        Retorna True si no se encontraron anomalías.
        Retorna False si se encontraron y repararon.

        Uso en ensure_ready():
        ```python
        if not PathHealthIntegration.check_and_repair(session, user_id, content_type):
            logger.info("[ensure_ready] Path had anomalies but were repaired. Restarting flow...")
            return  # Déjalo para el próximo call
        ```
        """
        try:
            monitor = PathHealthMonitor(session)
            anomalies = monitor.check_path_health(user_id, content_type)

            if not anomalies:
                return True  # No anomalies found

            # Anomalías detectadas - intentar reparar
            logger.warning(
                f"[PathHealthIntegration] Found {len(anomalies)} anomalies for user {user_id} ({content_type}). "
                f"Attempting auto-repair..."
            )

            repair_service = PathRepairService(session)
            repaired_count = 0

            for anomaly in anomalies:
                monitor.log_anomaly(anomaly)
                success = repair_service.repair_anomaly(anomaly)
                if success:
                    repaired_count += 1
                    logger.info(
                        f"[PathHealthIntegration] Repaired: {anomaly.anomaly_type}"
                    )
                else:
                    logger.warning(
                        f"[PathHealthIntegration] Failed to repair: {anomaly.anomaly_type}"
                    )

            logger.info(
                f"[PathHealthIntegration] Auto-repair completed: {repaired_count}/{len(anomalies)} anomalies fixed"
            )

            return False  # Anomalies were found and repaired

        except Exception as e:
            logger.error(
                f"[PathHealthIntegration] Error checking/repairing path: {str(e)}"
            )
            return True  # Return True to continue with normal flow (don't block)

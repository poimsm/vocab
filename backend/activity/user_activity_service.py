"""
Servicio para registrar y gestionar actividades del usuario.
"""
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
import json

from models import UserActivity, ActivityType, User
from logging_client import logger


class UserActivityService:
    """Gestor centralizado de actividades del usuario."""

    @staticmethod
    def log_activity(
        db: Session,
        user_id: int,
        activity_type: ActivityType,
        activity_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> UserActivity:
        """
        Registra una actividad del usuario.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            activity_type: Tipo de actividad (BUTTON_CLICK, ENDPOINT_VISIT, etc)
            activity_name: Nombre descriptivo de la actividad
            details: Datos adicionales en formato dict (se serializa a JSON)

        Returns:
            UserActivity: La actividad registrada
        """
        try:
            # Convertir details a JSON string si es necesario
            details_json = None
            if details:
                details_json = json.dumps(details)

            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type.value if isinstance(activity_type, ActivityType) else activity_type,
                activity_name=activity_name,
                details=details_json,
            )

            db.add(activity)
            db.commit()
            db.refresh(activity)

            logger.info(
                f"Activity logged: user_id={user_id}, type={activity_type}, name={activity_name}"
            )
            return activity

        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}")
            db.rollback()
            raise

    @staticmethod
    def log_button_click(
        db: Session,
        user_id: int,
        button_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> UserActivity:
        """
        Registra un click en un botón.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            button_name: Nombre del botón clickeado
            details: Datos adicionales

        Returns:
            UserActivity: La actividad registrada
        """
        return UserActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.BUTTON_CLICK,
            activity_name=button_name,
            details=details,
        )

    @staticmethod
    def log_endpoint_visit(
        db: Session,
        user_id: int,
        endpoint: str,
        method: str = "GET",
        details: Optional[Dict[str, Any]] = None,
    ) -> UserActivity:
        """
        Registra una visita a un endpoint.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            endpoint: Path del endpoint (ej: "/examples/next")
            method: Método HTTP (GET, POST, etc)
            details: Datos adicionales (parámetros, respuesta, etc)

        Returns:
            UserActivity: La actividad registrada
        """
        activity_name = f"{method}_{endpoint}"
        return UserActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.ENDPOINT_VISIT,
            activity_name=activity_name,
            details=details,
        )

    @staticmethod
    def log_page_view(
        db: Session,
        user_id: int,
        page_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> UserActivity:
        """
        Registra una vista de página.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            page_name: Nombre de la página (ej: "examples", "words", "dashboard")
            details: Datos adicionales

        Returns:
            UserActivity: La actividad registrada
        """
        return UserActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.PAGE_VIEW,
            activity_name=page_name,
            details=details,
        )

    @staticmethod
    def log_feature_interaction(
        db: Session,
        user_id: int,
        feature_name: str,
        interaction_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> UserActivity:
        """
        Registra una interacción con una característica.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            feature_name: Nombre de la característica (ej: "learning_path", "favorites")
            interaction_type: Tipo de interacción (ej: "open", "filter", "sort")
            details: Datos adicionales

        Returns:
            UserActivity: La actividad registrada
        """
        activity_name = f"{feature_name}_{interaction_type}"
        return UserActivityService.log_activity(
            db=db,
            user_id=user_id,
            activity_type=ActivityType.FEATURE_INTERACTION,
            activity_name=activity_name,
            details=details,
        )

    @staticmethod
    def get_user_activities(
        db: Session,
        user_id: int,
        limit: int = 100,
        activity_type: Optional[ActivityType] = None,
        hours: Optional[int] = None,
    ) -> List[UserActivity]:
        """
        Obtiene actividades del usuario.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            limit: Número máximo de registros a obtener
            activity_type: Filtrar por tipo de actividad (opcional)
            hours: Filtrar actividades de las últimas N horas (opcional)

        Returns:
            List[UserActivity]: Lista de actividades
        """
        query = select(UserActivity).where(UserActivity.user_id == user_id)

        if activity_type:
            query = query.where(UserActivity.activity_type == activity_type)

        if hours:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            query = query.where(UserActivity.created_at >= cutoff_time)

        query = query.order_by(UserActivity.created_at.desc()).limit(limit)

        return db.exec(query).all()

    @staticmethod
    def get_activity_stats(
        db: Session,
        user_id: int,
        hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Obtiene estadísticas de actividades del usuario.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            hours: Período a considerar (últimas N horas)

        Returns:
            Dict: Estadísticas de actividades
        """
        query = select(UserActivity).where(UserActivity.user_id == user_id)

        if hours:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            query = query.where(UserActivity.created_at >= cutoff_time)

        activities = db.exec(query).all()

        # Contar por tipo
        stats_by_type = {}
        for activity_type in ActivityType:
            count = sum(1 for a in activities if a.activity_type == activity_type)
            if count > 0:
                stats_by_type[activity_type.value] = count

        # Actividades más frecuentes
        activity_names = {}
        for activity in activities:
            activity_names[activity.activity_name] = (
                activity_names.get(activity.activity_name, 0) + 1
            )

        top_activities = sorted(
            activity_names.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "total_activities": len(activities),
            "by_type": stats_by_type,
            "top_activities": [
                {"name": name, "count": count} for name, count in top_activities
            ],
        }

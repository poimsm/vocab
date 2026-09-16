"""
Rutas para rastrear y gestionar actividades del usuario.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Optional, Any, Dict, List
from pydantic import BaseModel

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User, ActivityType, UserActivity
from decorators import log_endpoint
from activity.user_activity_service import UserActivityService


class LogActivityRequest(BaseModel):
    """Request para registrar una actividad."""
    activity_type: str  # "button_click", "endpoint_visit", "page_view", "feature_interaction"
    activity_name: str
    details: Optional[Dict[str, Any]] = None


class ButtonClickRequest(BaseModel):
    """Request para registrar un click de botón."""
    button_name: str
    details: Optional[Dict[str, Any]] = None


class PageViewRequest(BaseModel):
    """Request para registrar una vista de página."""
    page_name: str
    details: Optional[Dict[str, Any]] = None


class FeatureInteractionRequest(BaseModel):
    """Request para registrar una interacción con feature."""
    feature_name: str
    interaction_type: str
    details: Optional[Dict[str, Any]] = None


class ActivityResponse(BaseModel):
    """Response de una actividad."""
    id: int
    user_id: int
    activity_type: str
    activity_name: str
    details: Optional[str]
    created_at: str


class ActivityStatsResponse(BaseModel):
    """Response de estadísticas de actividades."""
    total_activities: int
    by_type: Dict[str, int]
    top_activities: List[Dict[str, Any]]


router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("/log")
@log_endpoint
async def log_activity(
    request: LogActivityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Registra una actividad del usuario.

    Permite registrar cualquier tipo de actividad con datos personalizados.
    """
    try:
        # Validar que el tipo de actividad sea válido
        try:
            activity_type = ActivityType(request.activity_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid activity_type. Must be one of: {', '.join([t.value for t in ActivityType])}",
            )

        activity = UserActivityService.log_activity(
            db=db,
            user_id=current_user.id,
            activity_type=activity_type,
            activity_name=request.activity_name,
            details=request.details,
        )

        return {
            "success": True,
            "activity_id": activity.id,
            "message": "Activity logged successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")
        raise HTTPException(status_code=500, detail="Error logging activity")


@router.post("/button-click")
@log_endpoint
async def log_button_click(
    request: ButtonClickRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Registra un click en un botón del frontend.

    Ejemplo: /activities/button-click
    {
        "button_name": "learn_button",
        "details": {"word_id": 123, "action": "mark_as_learned"}
    }
    """
    try:
        activity = UserActivityService.log_button_click(
            db=db,
            user_id=current_user.id,
            button_name=request.button_name,
            details=request.details,
        )

        return {
            "success": True,
            "activity_id": activity.id,
            "message": "Button click logged successfully",
        }

    except Exception as e:
        logger.error(f"Error logging button click: {str(e)}")
        raise HTTPException(status_code=500, detail="Error logging button click")


@router.post("/page-view")
@log_endpoint
async def log_page_view(
    request: PageViewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Registra cuando el usuario accede a una página.

    Ejemplo: /activities/page-view
    {
        "page_name": "examples",
        "details": {"section": "explore", "filters": {"level": "intermediate"}}
    }
    """
    try:
        activity = UserActivityService.log_page_view(
            db=db,
            user_id=current_user.id,
            page_name=request.page_name,
            details=request.details,
        )

        return {
            "success": True,
            "activity_id": activity.id,
            "message": "Page view logged successfully",
        }

    except Exception as e:
        logger.error(f"Error logging page view: {str(e)}")
        raise HTTPException(status_code=500, detail="Error logging page view")


@router.post("/feature-interaction")
@log_endpoint
async def log_feature_interaction(
    request: FeatureInteractionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Registra una interacción con una característica.

    Ejemplo: /activities/feature-interaction
    {
        "feature_name": "learning_path",
        "interaction_type": "filter_by_level",
        "details": {"level": "advanced", "results": 45}
    }
    """
    try:
        activity = UserActivityService.log_feature_interaction(
            db=db,
            user_id=current_user.id,
            feature_name=request.feature_name,
            interaction_type=request.interaction_type,
            details=request.details,
        )

        return {
            "success": True,
            "activity_id": activity.id,
            "message": "Feature interaction logged successfully",
        }

    except Exception as e:
        logger.error(f"Error logging feature interaction: {str(e)}")
        raise HTTPException(status_code=500, detail="Error logging feature interaction")


@router.get("/")
@log_endpoint
async def get_activities(
    limit: int = 100,
    activity_type: Optional[str] = None,
    hours: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Obtiene el historial de actividades del usuario.

    Parámetros:
    - limit: Número máximo de registros (default: 100)
    - activity_type: Filtrar por tipo de actividad (opcional)
    - hours: Filtrar actividades de las últimas N horas (opcional)

    Ejemplo: /activities/?limit=50&activity_type=button_click&hours=24
    """
    try:
        # Validar activity_type si se proporciona
        activity_type_enum = None
        if activity_type:
            try:
                activity_type_enum = ActivityType(activity_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid activity_type. Must be one of: {', '.join([t.value for t in ActivityType])}",
                )

        activities = UserActivityService.get_user_activities(
            db=db,
            user_id=current_user.id,
            limit=limit,
            activity_type=activity_type_enum,
            hours=hours,
        )

        return {
            "success": True,
            "count": len(activities),
            "activities": [
                {
                    "id": a.id,
                    "activity_type": a.activity_type.value,
                    "activity_name": a.activity_name,
                    "details": a.details,
                    "created_at": a.created_at.isoformat(),
                }
                for a in activities
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting activities: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting activities")


@router.get("/stats")
@log_endpoint
async def get_activity_stats(
    hours: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Obtiene estadísticas de actividades del usuario.

    Parámetros:
    - hours: Período a considerar (últimas N horas, optional)

    Ejemplo: /activities/stats?hours=24
    """
    try:
        stats = UserActivityService.get_activity_stats(
            db=db,
            user_id=current_user.id,
            hours=hours,
        )

        return {
            "success": True,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Error getting activity stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting activity stats")

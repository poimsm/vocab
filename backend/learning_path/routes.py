from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from logging_client import logger
from db import get_db
from auth.repository import get_current_user
from models import User, ContentType
from decorators import log_endpoint
from learning_path.content_planner import ContentPlanner
from learning_path.priority_engine import PriorityEngine
from learning_path.content_queue import ContentQueue
from examples.repository import ExampleRepository
from best_options.repository import BestOptionRepository
from words.word_repository import WordRepository


router = APIRouter()


@router.post("/prepare/{content_type}", status_code=status.HTTP_202_ACCEPTED)
@log_endpoint
def prepare_content(
    content_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Prepara contenido para el usuario (dispara ContentPlanner)"""

    logger.info(f"[prepare_content] User {current_user.id}: Preparing {content_type}")

    try:
        # Validar tipo de contenido
        if content_type.lower() == "example":
            ct = ContentType.EXAMPLE
        elif content_type.lower() == "best_options":
            ct = ContentType.BEST_OPTIONS
        else:
            return {
                "status": "error",
                "message": f"Invalid content type: {content_type}"
            }

        # Instanciar dependencias
        word_repo = WordRepository(db)
        example_repo = ExampleRepository(db)
        best_option_repo = BestOptionRepository(db)
        priority_engine = PriorityEngine()
        content_queue = ContentQueue(db)

        # Crear planner y ejecutar
        planner = ContentPlanner(
            session=db,
            priority_engine=priority_engine,
            content_queue=content_queue,
            word_repository=word_repo,
            example_repository=example_repo,
            best_option_repository=best_option_repo,
        )

        planner.ensure_ready(
            user_id=current_user.id,
            content_type=ct,
        )

        logger.info(f"[prepare_content] Content prepared for user {current_user.id}")

        return {
            "status": "ok",
            "message": f"Content preparation triggered for {content_type}"
        }

    except Exception as e:
        logger.error(
            f"[prepare_content] Error preparing content for user {current_user.id}: {e}",
            exc_info=True
        )
        return {
            "status": "error",
            "message": str(e)
        }

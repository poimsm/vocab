
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from auth.models import User
from features.examples.models import Example
from decorators import log_endpoint
from core.enums import ContentType
from features.examples.schemas import ExploreResponse, FavoritesResponse
from core.explore.explore_actions import ExploreActions
from features.examples.explore_response_builder import ExploreResponseBuilder
from features.examples.repository import ExampleRepository
from core.delivery.service import DeliveryService
from activity.user_activity_service import UserActivityService


class ExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], ["sync"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 5  # Para la acción "next"
    buffer_delivery_ids: List[int] = []  # IDs actuales del buffer
    buffer_position: int = 0  # Posición actual en el buffer


router = APIRouter()




@router.post("/explore", response_model=ExploreResponse)
@log_endpoint
def explore_examples(
    request: ExploreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint unificado con acciones encadenables y buffer management.

    Delega la lógica a ExploreActions de core/explore/explore_actions.py.
    Usa LearningPathService para validar contenido disponible y triggear generación.

    Acciones disponibles:
    - "resolve": Resuelve un item (registra exposición) - requiere resolve_queue_item_id
    - "sync": Solo sincroniza la posición actual (sin tocar el buffer)
    - "sync-buffer": Valida y refill el buffer (para llenar después de marcar palabra como learned)
    - "resume": Resume sesión - carga nuevo buffer si todos fueron visitados, sino continúa
    - "next": Descarta buffer completamente, limpia visitados, carga nuevos items y posición=0
    """
    logger.info(
        f"[explore_examples] User {current_user.id}: actions={request.actions}, "
        f"limit={request.limit}, buffer_size={len(request.buffer_delivery_ids)}"
    )

    # Log de actividad
    UserActivityService.log_feature_interaction(
        db=db,
        user_id=current_user.id,
        feature_name="examples_explore",
        interaction_type="_".join(request.actions),
        details={
            "actions": request.actions,
            "limit": request.limit,
            "buffer_size": len(request.buffer_delivery_ids)
        }
    )

    try:
        from features.content_repository import UnifiedContentRepository
        content_repo = UnifiedContentRepository(db)

        # Crear validador agnóstico usando ExampleRepository
        class ExampleContentValidator:
            def __init__(self, example_repo):
                self.example_repo = example_repo

            def is_content_learned(self, content_id: int, user_id: int) -> bool:
                return self.example_repo.is_example_learned(content_id, user_id)

        content_validator = ExampleContentValidator(ExampleRepository(db))

        explore_actions = ExploreActions(
            db,
            content_repo=content_repo,
            content_validator=content_validator
        )
        status, buffer_ids, buffer_position = explore_actions.execute_actions(
            user_id=current_user.id,
            actions=request.actions,
            content_type=ContentType.EXAMPLE,
            resolve_queue_item_id=request.resolve_queue_item_id,
            limit=request.limit,
            buffer_delivery_ids=request.buffer_delivery_ids,
            buffer_position=request.buffer_position,
        )
    except ValueError as e:
        logger.error(f"[explore_examples] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    # Build examples response using ExploreResponseBuilder
    examples = []
    if buffer_ids:
        delivery_service = DeliveryService(db)
        delivery_items = delivery_service.get_delivery_items_by_ids(buffer_ids, current_user.id)
        delivery_item_map = {item.id: item for item in delivery_items}

        response_builder = ExploreResponseBuilder(db)
        examples = response_builder.build_examples_response(buffer_ids, delivery_item_map, current_user.id)

    logger.info(
        f"[explore_examples] Completed with status={status}, returned {len(examples)} examples, "
        f"buffer_size={len(buffer_ids)}, position={buffer_position}"
    )

    return {
        "examples": examples,
        "buffer_delivery_ids": buffer_ids,
        "buffer_position": buffer_position,
        "status": status,
    }



@router.patch("/{example_id}/toggle-favorite")
@log_endpoint
def toggle_example_favorite(
    example_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Alterna el estado de favorito de un ejemplo.

    Cuando se marca como favorito:
    - Se resetea is_marked a False
    - Se actualiza favorited_at (aparecerá primero en listado)

    Retorna: is_favorite, is_marked, unmarked_favorites_count
    """
    logger.info(f"[toggle_example_favorite] User {current_user.id}: Toggling favorite for example {example_id}")

    example_repo = ExampleRepository(db)
    is_favorite = example_repo.toggle_favorite(current_user.id, example_id)

    # Obtener el ejemplo actualizado para devolver el estado is_marked
    example = db.exec(
        select(Example).where(Example.id == example_id)
    ).first()

    if not example:
        raise HTTPException(status_code=404, detail="Example not found")

    logger.debug(f"[toggle_example_favorite] Example {example_id} is_favorite: {is_favorite}, is_marked: {example.is_marked}")

    # Log de actividad
    UserActivityService.log_button_click(
        db=db,
        user_id=current_user.id,
        button_name="toggle_example_favorite",
        details={
            "example_id": example_id,
            "is_favorite": is_favorite,
            "is_marked": example.is_marked
        }
    )

    # Obtener el contador actualizado de favoritos no marcados
    unmarked_count = example_repo.count_unmarked_favorites(current_user.id)

    return {
        "example_id": example_id,
        "is_favorite": is_favorite,
        "is_marked": example.is_marked,
        "unmarked_favorites_count": unmarked_count
    }


@router.patch("/{example_id}/toggle-marked")
@log_endpoint
def toggle_example_marked(
    example_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Alterna el estado de marcado de un ejemplo.

    Retorna el nuevo estado de is_marked.
    """
    logger.info(f"[toggle_example_marked] User {current_user.id}: Toggling marked status for example {example_id}")

    example_repo = ExampleRepository(db)
    is_marked = example_repo.toggle_marked(current_user.id, example_id)

    logger.debug(f"[toggle_example_marked] Example {example_id} is_marked: {is_marked}")

    # Log de actividad
    UserActivityService.log_button_click(
        db=db,
        user_id=current_user.id,
        button_name="toggle_example_marked",
        details={
            "example_id": example_id,
            "is_marked": is_marked
        }
    )

    # Obtener el contador actualizado de favoritos no marcados
    example_repo = ExampleRepository(db)
    unmarked_count = example_repo.count_unmarked_favorites(current_user.id)

    return {
        "example_id": example_id,
        "is_marked": is_marked,
        "unmarked_favorites_count": unmarked_count
    }


@router.get("/favorites", response_model=FavoritesResponse)
@log_endpoint
def get_favorite_examples(
    page: int = 1,
    limit: int = 15,
    is_marked: Optional[bool] = None,
    sort_by: str = 'not_marked_first',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene ejemplos marcados como favoritos con paginación.

    Parámetros:
    - page: Número de página
    - limit: Items por página
    - is_marked: Filtrar por estado de marcado (true/false/null) - DEPRECATED, usar sort_by
    - sort_by: Modo de ordenamiento ('done', 'random', 'not_marked_first')
        - 'done': Solo favoritos marcados
        - 'not_marked_first': Todos, primero no marcados
        - 'random': Solo no marcados en orden aleatorio

    Retorna:
    - items: Lista de ejemplos favoritos con texto segmentado
    - total: Total de ejemplos favoritos
    - page: Página actual
    - limit: Items por página
    - pages: Total de páginas
    - status: "ok"
    """
    logger.info(f"[get_favorite_examples] User {current_user.id}: Fetching favorite examples (page={page}, limit={limit}, is_marked={is_marked}, sort_by={sort_by})")

    # Log de actividad
    UserActivityService.log_page_view(
        db=db,
        user_id=current_user.id,
        page_name="examples_favorites",
        details={
            "page": page,
            "limit": limit,
            "sort_by": sort_by
        }
    )

    example_repo = ExampleRepository(db)
    paginated_data = example_repo.get_examples(current_user.id, page=page, limit=limit, is_marked=is_marked, sort_by=sort_by)

    # Segmentar el texto de cada ejemplo
    examples_response = []
    for example in paginated_data["items"]:
        text_segments = example_repo.segment_example_text(example)
        extracted_words = []  # Por ahora vacío, se puede implementar después
        examples_response.append({
            "id": example.id,
            "text": text_segments,
            "extracted_words": extracted_words,
            "is_favorite": example.is_favorite,
            "is_marked": example.is_marked
        })

    logger.debug(f"[get_favorite_examples] Retrieved {len(examples_response)} favorite examples")

    return {
        "items": examples_response,
        "total": paginated_data["total"],
        "page": paginated_data["page"],
        "limit": paginated_data["limit"],
        "pages": paginated_data["pages"],
        "status": "ok"
    }


@router.get("/favorites/count")
@log_endpoint
def get_favorites_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el contador de ejemplos favoritos no marcados del usuario.

    Retorna:
    - count: Total de ejemplos donde is_favorite=True e is_marked=False
    - status: "ok"
    """
    logger.info(f"[get_favorites_count] User {current_user.id}: Fetching unmarked favorites count")

    example_repo = ExampleRepository(db)
    count = example_repo.count_unmarked_favorites(current_user.id)

    logger.debug(f"[get_favorites_count] User {current_user.id} has {count} unmarked favorites")

    return {
        "count": count,
        "status": "ok"
    }


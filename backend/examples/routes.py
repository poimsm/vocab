
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select, func

from db import get_db
from logging_client import logger
from schemas.explore import ExploreResponse
from auth.repository import get_current_user
from models import User, ExampleWord
from decorators import log_endpoint
from examples import repository as ExampleRepository
from generation.queue.processor import GenerationProcessor
from generation.queue.example_generation_strategy import ExampleGenerationStrategy
from generation.queue import repository as QueueRepository


router = APIRouter()


@router.get("/examples")
@log_endpoint
def get_examples(
    sort: str = "newest",
    word_id: int = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
):
    logger.info(f"[get_examples] Fetching examples (sort={sort}, word_id={word_id}, page={page}, limit={limit})")
    paginated_data = ExampleRepository.get(
        db, sort=sort, word_id=word_id, page=page, limit=limit
    )
    logger.debug(f"[get_examples] Retrieved {len(paginated_data['items'])} examples")

    paginated_data["items"] = [
        {
            "id": e.id,
            "text": e.text,
            "is_favorite": e.is_favorite,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form,
                }
                for ew in e.example_words
            ],
        }
        for e in paginated_data["items"]
    ]

    return paginated_data


@router.patch("/{example_id}/toggle-active")
@log_endpoint
def toggle_example_active(example_id: int, db: Session = Depends(get_db)):
    logger.debug(f"[toggle_example_active] Toggling active status for example {example_id}")
    example = ExampleRepository.toggle_active(db, example_id)

    if not example:
        logger.warning(f"[toggle_example_active] Example {example_id} not found")
        raise HTTPException(status_code=404, detail="example not found")

    status = "activated" if example.is_active else "deactivated"
    logger.info(f"[toggle_example_active] Example {example_id} {status}")
    return {"message": f"example {status}"}


@router.patch("/{example_id}/toggle-fav")
@log_endpoint
def toggle_example_favorite(example_id: int, db: Session = Depends(get_db)):
    logger.debug(f"[toggle_example_favorite] Toggling favorite status for example {example_id}")
    example = ExampleRepository.toggle_favorite(db, example_id)

    if not example:
        logger.warning(f"[toggle_example_favorite] Example {example_id} not found")
        raise HTTPException(status_code=404, detail="example not found")

    logger.info(f"[toggle_example_favorite] Example {example_id} marked as {'favorited' if example.is_favorite else 'not favorited'}")
    return {
        "id": example.id,
        "is_favorite": example.is_favorite,
        "message": f"example marked as {'favorited' if example.is_favorite else 'not favorited'}",
    }


@router.get("/explore", response_model=ExploreResponse)
@log_endpoint
def get_explore_feed(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    processor = GenerationProcessor(
        db,
        current_user.id,
        ExampleGenerationStrategy
    )
    try:
        logger.debug(f"[get_explore_feed] Calling processor.process(limit={limit})")
        result = processor.process(limit)
        logger.debug(f"[get_explore_feed] Processor returned status: {result.get('status')}, items count: {len(result.get('items', []))}")

        # Transformar items si hay
        if result.get("items") and isinstance(result["items"], list) and result.get("status") != "error":
            from models import Example, QueueStatus
            from sqlalchemy.orm import joinedload

            examples = []
            for item in result["items"]:
                if hasattr(item, 'id'):
                    # Cargar el ejemplo con sus palabras asociadas
                    example = db.exec(
                        select(Example)
                        .where(Example.id == item.content_id)
                        .options(joinedload(Example.example_words).joinedload(ExampleWord.word))
                    ).unique().first()

                    if example:
                        # Cambiar estado a SENT al devolver al frontend ANTES de segmentar
                        item.status = QueueStatus.SENT
                        db.add(item)
                        db.flush()  # Flush to save changes but don't commit yet

                        try:
                            # Extraer datos del ejemplo antes de usarlos
                            example_text = example.text
                            example_words_data = []
                            for ew in example.example_words:
                                example_words_data.append({
                                    'text_form': ew.text_form,
                                    'word_id': ew.word_id,
                                    'word': {
                                        'id': ew.word.id,
                                        'main': ew.word.main,
                                        'type': ew.word.type,
                                        'meaning': ew.word.meaning,
                                        'level': ew.word.level,
                                        'is_boosted': ew.word.is_boosted,
                                        'batch_id': ew.word.batch_id,
                                    }
                                })

                            # Segmentar el texto del ejemplo con datos extraídos
                            text_segments = ExampleRepository.segment_example_text(
                                example_text,
                                example_words_data
                            )

                            examples.append({
                                "id": item.id,
                                "text": text_segments
                            })
                        except Exception as seg_error:
                            logger.error(f"[get_explore_feed] Error segmenting example {item.content_id}: {seg_error}", exc_info=True)
                            # Continuar sin este ejemplo si hay error en segmentación
                            continue

            db.commit()
            result["examples"] = examples
            del result["items"]
        else:
            # Si no hay items, retornar examples vacío
            result["examples"] = []
            if "items" in result:
                del result["items"]

        return result
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        logger.error(f"[get_explore_feed] FULL ERROR:\n{full_traceback}")
        logger.error(f"[get_explore_feed] Error type: {type(e).__name__}")
        logger.error(f"[get_explore_feed] Error message: {str(e)}")
        return {"status": "error", "examples": []}
    


@router.patch("/{queue_item_id}/resolve")
@log_endpoint
def resolve_queue_item(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.debug(f"[resolve_queue_item] User {current_user.id}: Resolving queue item {queue_item_id}")

    queue_item = QueueRepository.get_by_id(db, queue_item_id)
    if not queue_item:
        logger.warning(f"[resolve_queue_item] Queue item {queue_item_id} not found")
        raise HTTPException(status_code=404, detail="Queue item not found")

    QueueRepository.mark_resolved(db, queue_item_id)

    example_id = queue_item.content_id
    example = ExampleRepository.increment_statistics(db, example_id=example_id, user_id=current_user.id)

    if not example:
        logger.warning(f"[resolve_queue_item] Example {example_id} not found")
        raise HTTPException(
            status_code=404,
            detail="Example not found or no longer pending",
        )

    logger.info(f"[resolve_queue_item] Example {example_id} resolved. Times seen: {example.times_seen}")
    return {
        "id": example.id,
        "message": "The example is no longer pending. Views successfully incremented.",
    }


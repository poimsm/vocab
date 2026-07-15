from sqlmodel import Session
from fastapi import HTTPException, Query, Body, APIRouter, Depends
from sqlmodel import Session
from logging_config import logger
from db import get_db
import crud
import ai
import math
import random
from typing import List, Set
import collections

router = APIRouter()


@router.get("/examples")
def get_examples(
    sort: str = "newest",
    word_id: int = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db)  # CAMBIO: Tipado de sesión
):
    paginated_data = crud.get_examples(
        db, sort=sort, word_id=word_id, page=page, limit=limit
    )

    paginated_data["items"] = [
        {
            "id": e.id,
            "text": e.text,
            "is_favorite": e.is_favorite,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form
                }
                for ew in e.example_words
            ]
        }
        for e in paginated_data["items"]
    ]

    return paginated_data


@router.post("/generate")
def generate_examples(
    word_id: int = Body(None, embed=True),
    db: Session = Depends(get_db)
):
    # CASO 1: Viene un word_id
    if word_id is not None:
        word = crud.get_word_by_id(db, word_id)
        if not word:
            raise HTTPException(
                status_code=404, detail="Palabra no encontrada")

        # 🔥 DOBLE CHEQUEO: Si la palabra ya está muy vista, la desviamos a una menos vista al azar
        UMBRAL_VISUALIZACIONES = 5
        if word.times_seen >= UMBRAL_VISUALIZACIONES:
            # Traemos un grupo de candidatas menos vistas y elegimos una al azar
            candidatas = crud.get_words_least_seen(db, limit=10)
            if candidatas:
                word = random.choice(candidatas)

        raw_strings = ai.generate_examples_for_single_word(word, amount=3)
        if not raw_strings:
            raise HTTPException(
                status_code=500, detail="Error generando ejemplos con IA"
            )

        raw_examples = [
            {
                "text": text_string,
                "words": [{"word_id": word.id, "word": word.main}]
            }
            for text_string in raw_strings
        ]

        words_to_increment = [word]

    # CASO 2: No viene word_id (Mantiene tu lógica actual)
    else:
        words_to_increment = crud.get_words_least_seen(db)
        if not words_to_increment:
            return []

        raw_examples = ai.generate_examples_from_words(words_to_increment)

    examples = crud.create_examples(db, raw_examples)
    crud.increment_words_seen(db, words_to_increment)

    return [{"id": e.id, "text": e.text} for e in examples]


@router.get("/random")
def get_random_examples(db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
    words = crud.get_words_least_seen(db, 4)
    if not words:
        return []

    word_ids = [w.id for w in words]
    examples = crud.get_random_examples_by_words(db, word_ids=word_ids)

    crud.increment_words_seen(db, words)

    return [
        {
            "id": e.id,
            "text": e.text,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form
                }
                for ew in e.example_words
            ]
        }
        for e in examples
    ]


@router.patch("/{example_id}/toggle-active")
# CAMBIO: Tipado de sesión
def toggle_example_active(example_id: int, db: Session = Depends(get_db)):
    example = crud.toggle_example_active(db, example_id)

    if not example:
        raise HTTPException(status_code=404, detail="example not found")

    status = "activated" if example.is_active else "deactivated"
    return {"message": f"example {status}"}


@router.patch("/{example_id}/toggle-fav")
# CAMBIO: Tipado de sesión
def toggle_example_favorite(example_id: int, db: Session = Depends(get_db)):
    example = crud.toggle_example_favorite(db, example_id)

    if not example:
        raise HTTPException(status_code=404, detail="example not found")

    return {
        "id": example.id,
        "is_favorite": example.is_favorite,
        "message": f"example marked as {'favorited' if example.is_favorite else 'not favorited'}"
    }


@router.post("/explore2")
def explore_examples(
    total_amount: int = Body(
        15, ge=3, le=20, description="Total de ejemplos a retornar", embed=True),
    db: Session = Depends(get_db)
):
    # 1. Intentar obtener los ejemplos directamente de la cola
    raw_queue_examples = crud.get_examples_from_queue(
        db, limit=total_amount * 2)  # Pedimos de más para tener margen de filtrado

    filtered_examples = []
    MAX_VISTAS_PERMITIDAS = 5  # Umbral para congelar palabras muy vistas

    # 2. Doble chequeo: Filtrar ejemplos con palabras muy visualizadas
    for e in raw_queue_examples:
        contaminado = False
        for ew in e.example_words:
            if ew.word.times_seen > MAX_VISTAS_PERMITIDAS:
                contaminado = True
                break

        if not contaminado:
            filtered_examples.append(e)

        if len(filtered_examples) >= total_amount:
            break

    # 3. Calcular si nos quedamos cortos debido al filtro (déficit)
    deficit = total_amount - len(filtered_examples)

    # 4. Si faltan ejemplos limpios, disparamos el método de rellenado (refill)
    if deficit > 0:
        crud.refill_example_queue(db)

        # Volvemos a consultar la cola para extraer los faltantes
        extra_examples = crud.get_examples_from_queue(db, limit=deficit * 2)

        for e in extra_examples:
            contaminado = False
            for ew in e.example_words:
                if ew.word.times_seen > MAX_VISTAS_PERMITIDAS:
                    contaminado = True
                    break
            if not contaminado:
                filtered_examples.append(e)
            if len(filtered_examples) >= total_amount:
                break

    # Fallback: Si el filtro fue demasiado estricto y dejó la respuesta vacía,
    # usamos lo que haya en la cola original para no romper la UX
    if not filtered_examples and raw_queue_examples:
        filtered_examples = raw_queue_examples[:total_amount]

    if filtered_examples:
        db.commit()
        for e in filtered_examples:
            db.refresh(e)

    # 5. Mapear respuesta unificada al usuario
    return [
        {
            "id": e.id,
            "text": e.text,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form
                }
                for ew in e.example_words
            ]
        }
        for e in filtered_examples
    ]


@router.post("/explore")
def explore_examples(
    total_amount: int = Body(
        15, ge=3, le=20, description="Total de ejemplos a retornar", embed=True),
    db: Session = Depends(get_db)
):
    # 1. Traemos un pool generoso de la cola para tener de dónde elegir y filtrar
    # Pedimos el triple del tamaño solicitado para garantizar diversidad
    raw_queue_examples = crud.get_examples_from_queue(
        db, limit=total_amount * 3)

    # Si la cola está vacía, hacemos un refill preventivo de inmediato
    if not raw_queue_examples:
        logger.info("Cola vacía al iniciar. Disparando refill preventivo.")
        crud.refill_example_queue(db)
        raw_queue_examples = crud.get_examples_from_queue(
            db, limit=total_amount * 3)

    # Helper para calcular la puntuación de un ejemplo
    # Queremos puntuaciones BAJAS (prioridad alta).
    # - Si tiene palabras con 0 vistas: Puntuación excelente (0-1)
    # - Si tiene palabras con > 5 vistas: Penalización alta (+10 por cada palabra "quemada")
    def calculate_example_score(example) -> float:
        if not example.example_words:
            return 999.0  # Sin palabras asociadas, prioridad ínfima

        views = [ew.word.times_seen for ew in example.example_words]
        min_views = min(views)
        avg_views = sum(views) / len(views)

        # Penalización por palabras que superan el límite óptimo (5 vistas)
        penalty = sum(15.0 for v in views if v > 5)

        # El score ideal premia que tenga palabras sin ver (min_views == 0)
        # y penaliza las palabras muy vistas.
        return min_views + (avg_views * 0.1) + penalty

    # 2. Lógica de selección inteligente con control de diversidad
    def select_balanced_examples(candidates, limit: int) -> List:
        # Ordenamos candidatos: los mejores scores (más bajos) van primero
        sorted_candidates = sorted(candidates, key=calculate_example_score)

        selected = []
        # Rastreador para evitar saturar el lote con la misma palabra
        # Permite máximo 2 ejemplos de la misma palabra en un lote de 15
        word_usage_counter = collections.Counter()
        MAX_REPETITIONS_PER_WORD = 2

        for e in sorted_candidates:
            # Analizamos si este ejemplo introduce palabras que ya hemos usado mucho en este lote
            has_overused_word = False
            for ew in e.example_words:
                if word_usage_counter[ew.word_id] >= MAX_REPETITIONS_PER_WORD:
                    has_overused_word = True
                    break

            # Si contiene una palabra ya muy repetida en esta respuesta, la saltamos temporalmente
            if has_overused_word:
                continue

            # Si pasa el filtro de diversidad, lo agregamos
            selected.append(e)
            for ew in e.example_words:
                word_usage_counter[ew.word_id] += 1

            if len(selected) >= limit:
                break

        # Si por ser estrictos con la diversidad no llenamos el cupo,
        # hacemos una segunda pasada relajando la regla de diversidad
        if len(selected) < limit:
            for e in sorted_candidates:
                if e not in selected:
                    selected.append(e)
                if len(selected) >= limit:
                    break

        return selected

    # Procesamos nuestra primera selección
    filtered_examples = select_balanced_examples(
        raw_queue_examples, total_amount)

    # 3. ¿Déficit? Si no alcanzamos el total_amount, hacemos refill y buscamos más
    deficit = total_amount - len(filtered_examples)
    if deficit > 0:
        logger.info(
            f"Déficit de {deficit} ejemplos. Ejecutando refill de la cola.")
        crud.refill_example_queue(db)

        # Traemos nuevos refuerzos
        extra_examples = crud.get_examples_from_queue(
            db, limit=total_amount * 3)

        # Unimos los ejemplos actuales con los nuevos asegurando no duplicar IDs físicos de ejemplos
        all_candidates = {e.id: e for e in (
            filtered_examples + extra_examples)}.values()

        # Volvemos a correr la selección balanceada sobre el pool completo agrandado
        filtered_examples = select_balanced_examples(
            all_candidates, total_amount)

    # 4. Guardar cambios (incrementar times_seen de las palabras que el usuario va a ver)
    if filtered_examples:
        try:
            # Registramos la visualización de las palabras incluidas en este lote
            for e in filtered_examples:
                for ew in e.example_words:
                    ew.word.times_seen += 1  # Incrementamos vista
                    db.add(ew.word)
            db.commit()

            # Refrescamos la sesión para devolver los datos actualizados
            for e in filtered_examples:
                db.refresh(e)
        except Exception as write_error:
            db.rollback()
            logger.error(
                f"Error al actualizar vistas de palabras: {write_error}")

    # 5. Mapear respuesta unificada al usuario
    return [
        {
            "id": e.id,
            "text": e.text,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form
                }
                for ew in e.example_words
            ]
        }
        for e in filtered_examples
    ]


@router.patch("/{example_id}/resolve-pending")
def resolve_example_pending(example_id: int, db: Session = Depends(get_db)):
    example = crud.resolve_and_increment_example(db, example_id)

    if not example:
        raise HTTPException(
            status_code=404,
            detail="Example no encontrado o ya no estaba marcado como pendiente"
        )

    return {
        "id": example.id,
        "times_seen": example.times_seen,
        "message": "El ejemplo ya no está pendiente. Visualizaciones incrementadas con éxito."
    }

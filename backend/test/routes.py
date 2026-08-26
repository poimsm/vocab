from fastapi import APIRouter, Body, Depends
from logging_client import logger
from decorators import log_endpoint
from pydantic import BaseModel
from sqlmodel import Session
from db import get_db

router = APIRouter()


class ApproximateTextFormRequest(BaseModel):
    example_text: str = Body(..., description="El texto del ejemplo")
    word_main: str = Body(..., description="La palabra base (simula word.main)")


@router.get("/nltk", response_model=dict)
@log_endpoint
def test_nltk():
    """
    Endpoint para probar que NLTK está correctamente instalado y los corpus descargados.
    """
    results = {
        "status": "error",
        "tests": {}
    }

    try:
        import nltk
        results["nltk_version"] = nltk.__version__
        results["nltk_path"] = nltk.data.path

        # Test 1: stopwords
        try:
            from nltk.corpus import stopwords
            english_stopwords = stopwords.words("english")
            results["tests"]["stopwords"] = {
                "status": "ok",
                "sample": english_stopwords[:10],
                "total": len(english_stopwords)
            }
        except Exception as e:
            results["tests"]["stopwords"] = {
                "status": "error",
                "error": str(e)
            }

        # Test 2: tokenize
        try:
            from nltk.tokenize import word_tokenize
            tokens = word_tokenize("Hello world, this is a test.")
            results["tests"]["tokenize"] = {
                "status": "ok",
                "result": tokens
            }
        except Exception as e:
            results["tests"]["tokenize"] = {
                "status": "error",
                "error": str(e)
            }

        # Test 3: wordnet
        try:
            from nltk.corpus import wordnet
            synsets = wordnet.synsets("dog")
            definition = synsets[0].definition() if synsets else None
            results["tests"]["wordnet"] = {
                "status": "ok",
                "synsets_count": len(synsets),
                "example_definition": definition
            }
        except Exception as e:
            results["tests"]["wordnet"] = {
                "status": "error",
                "error": str(e)
            }

        # Test 4: WordNetLemmatizer
        try:
            from nltk.stem import WordNetLemmatizer
            lemmatizer = WordNetLemmatizer()
            test_words = ["running", "ran", "runs", "burial", "buried", "quivering", "quivered"]
            lemmatized = {word: lemmatizer.lemmatize(word, pos='v') for word in test_words}
            results["tests"]["lemmatizer"] = {
                "status": "ok",
                "samples": lemmatized
            }
        except Exception as e:
            results["tests"]["lemmatizer"] = {
                "status": "error",
                "error": str(e)
            }

        # Test 5: approximate_text_form function
        try:
            from examples.helpers import approximate_text_form
            test_cases = [
                ("He bore the pain silently", "borne"),
                ("She buried her loved one", "burial"),
                ("They quivered at the thought", "quivering"),
            ]
            approximations = {
                case[1]: approximate_text_form(case[0], case[1])
                for case in test_cases
            }
            results["tests"]["approximate_text_form"] = {
                "status": "ok",
                "samples": approximations
            }
        except Exception as e:
            results["tests"]["approximate_text_form"] = {
                "status": "error",
                "error": str(e)
            }

        # Si todos los tests pasaron, cambiar status
        all_ok = all(
            test.get("status") == "ok"
            for test in results["tests"].values()
        )
        results["status"] = "ok" if all_ok else "partial"

    except Exception as e:
        results["error"] = str(e)
        logger.error(f"[test_nltk] Error: {e}", exc_info=True)

    return results


@router.post("/approximate-text-form", response_model=dict)
@log_endpoint
def test_approximate_text_form(request: ApproximateTextFormRequest):
    """
    Endpoint para probar la función approximate_text_form con texto y palabra personalizados.

    Simula cómo se extrae el text_form del ejemplo.
    """
    try:
        from examples.helpers import approximate_text_form

        example_text = request.example_text.strip()
        word_main = request.word_main.strip()

        if not example_text:
            return {
                "status": "error",
                "error": "example_text no puede estar vacío"
            }

        if not word_main:
            return {
                "status": "error",
                "error": "word_main no puede estar vacío"
            }

        # Aplicar la función
        result = approximate_text_form(example_text, word_main)

        return {
            "status": "ok",
            "input": {
                "example_text": example_text,
                "word_main": word_main
            },
            "output": {
                "text_form": result,
                "found_in_text": result.lower() in example_text.lower()
            }
        }

    except Exception as e:
        logger.error(f"[test_approximate_text_form] Error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/approximate-text-form-batch", response_model=dict)
@log_endpoint
def test_approximate_text_form_batch(test_cases: list = Body(..., description="Lista de casos para probar")):
    """
    Endpoint para probar multiple_text_form con un lote de casos de prueba.

    Formato esperado:
    [
        {"example_text": "...", "word_main": "..."},
        ...
    ]
    """
    try:
        from examples.helpers import approximate_text_form

        if not test_cases:
            return {
                "status": "error",
                "error": "test_cases no puede estar vacío"
            }

        results = []
        for idx, case in enumerate(test_cases):
            example_text = case.get("example_text", "").strip()
            word_main = case.get("word_main", "").strip()

            if not example_text or not word_main:
                results.append({
                    "index": idx,
                    "status": "skipped",
                    "reason": "example_text o word_main vacío"
                })
                continue

            try:
                text_form = approximate_text_form(example_text, word_main)
                results.append({
                    "index": idx,
                    "status": "ok",
                    "input": {
                        "example_text": example_text,
                        "word_main": word_main
                    },
                    "output": {
                        "text_form": text_form,
                        "found_in_text": text_form.lower() in example_text.lower()
                    }
                })
            except Exception as e:
                results.append({
                    "index": idx,
                    "status": "error",
                    "error": str(e)
                })

        return {
            "status": "ok",
            "total": len(test_cases),
            "results": results
        }

    except Exception as e:
        logger.error(f"[test_approximate_text_form_batch] Error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/fix-example-words", response_model=dict)
@log_endpoint
def fix_example_words(dry_run: bool = True, db: Session = Depends(get_db)):
    """
    Actualiza todos los ExampleWords en la BD usando approximate_text_form.

    Recalcula el text_form correcto de cada ExampleWord basado en:
    - example.text (el texto del ejemplo)
    - word.main (la palabra base)

    Parameters:
    - dry_run: Si es True, solo muestra los cambios sin actualizar. Si es False, actualiza la BD.

    Retorna:
    - total: cantidad total de ExampleWords procesados
    - updated: cantidad que fueron modificados
    - unchanged: cantidad que se mantuvieron iguales
    - errors: cantidad que tuvieron errores
    - changes: detalle de los cambios realizados (en dry_run)
    """
    try:
        from sqlmodel import select
        from models import ExampleWord, Example, Word
        from examples.helpers import approximate_text_form

        # Obtener todos los ExampleWords con sus relaciones
        statement = select(ExampleWord, Example, Word).join(
            Example, ExampleWord.example_id == Example.id
        ).join(
            Word, ExampleWord.word_id == Word.id
        )
        rows = db.exec(statement).all()

        if not rows:
            return {
                "status": "ok",
                "total": 0,
                "message": "No ExampleWords found in database"
            }

        total = len(rows)
        updated = 0
        unchanged = 0
        errors = 0
        changes = []

        for example_word, example, word in rows:
            try:
                # Calcular el nuevo text_form
                new_text_form = approximate_text_form(example.text, word.main)

                # Comparar con el actual
                if new_text_form != example_word.text_form:
                    changes.append({
                        "example_word_id": f"{example_word.example_id}:{example_word.word_id}",
                        "word_main": word.main,
                        "old_text_form": example_word.text_form,
                        "new_text_form": new_text_form,
                        "example_text": example.text
                    })

                    if not dry_run:
                        # Actualizar en BD
                        example_word.text_form = new_text_form
                        db.add(example_word)

                    updated += 1
                else:
                    unchanged += 1

            except Exception as e:
                logger.error(
                    f"[fix_example_words] Error processing ExampleWord {example_word.example_id}:{example_word.word_id}: {e}",
                    exc_info=True
                )
                errors += 1

        # Commit si no es dry_run
        if not dry_run and updated > 0:
            db.commit()
            logger.info(
                f"[fix_example_words] Updated {updated} ExampleWords in database"
            )

        return {
            "status": "ok",
            "dry_run": dry_run,
            "total": total,
            "updated": updated,
            "unchanged": unchanged,
            "errors": errors,
            "changes": changes if dry_run or updated <= 100 else changes[:100]  # Limitar a 100 para no sobrecargar
        }

    except Exception as e:
        logger.error(f"[fix_example_words] Error: {e}", exc_info=True)
        if not dry_run:
            db.rollback()
        return {
            "status": "error",
            "error": str(e)
        }

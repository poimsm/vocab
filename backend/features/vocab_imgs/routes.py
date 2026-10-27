"""Routes for Vocabulary Images feature"""
from logging_client import logger
from fastapi import APIRouter, Depends, HTTPException, Body, status, Path
from sqlmodel import Session, select
from db import get_db
from auth.models import User
from auth.repository import get_current_user
from decorators import log_endpoint
from features.words.repository import WordRepository
from features.words.models import Word
from features.vocab_imgs.models import VocabImage, VocabImageWord
from features.vocab_imgs.schemas import AddVocabImageWordRequest, AddVocabImageWordResponse
from activity.user_activity_service import UserActivityService
from config import QuotaValidator

router = APIRouter()


@router.post("/add-word", response_model=AddVocabImageWordResponse, status_code=status.HTTP_200_OK)
@log_endpoint
def add_vocab_image_word(
    request_data: AddVocabImageWordRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Adds a word from a vocabulary image theme.

    This endpoint creates or links a Word to a VocabImageWord.
    The vocab_image_word_id is stored in the Word model for reference.

    Body expected:
    {
        "vocab_image_word_id": "west-001",
        "word": "Outlaw",
        "definition": "A criminal who is wanted by law enforcement"
    }

    Response:
    - status: "success" - word added successfully
    - status: "existing" - word already added by this user
    - status: "error" - validation or creation error
    """

    logger.info(
        f"[add_vocab_image_word] User {current_user.id}: "
        f"Adding word '{request_data.word}' from vocab_image_word_id '{request_data.vocab_image_word_id}'"
    )

    # Log de actividad - inicio
    UserActivityService.log_feature_interaction(
        db=db,
        user_id=current_user.id,
        feature_name="vocab_images",
        interaction_type="word_add_started",
        details={
            "vocab_image_word_id": request_data.vocab_image_word_id,
            "word": request_data.word
        }
    )

    # Validar que el usuario no haya excedido su límite de palabras
    try:
        QuotaValidator.validate_max_words_per_user(db, current_user.id)
    except Exception as e:
        logger.warning(f"[add_vocab_image_word] Quota exceeded: {e}")
        UserActivityService.log_feature_interaction(
            db=db,
            user_id=current_user.id,
            feature_name="vocab_images",
            interaction_type="word_add_error_quota_exceeded",
            details={"word": request_data.word}
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Has reached maximum words limit"
        )

    try:
        # Verify that vocab_image_word_id exists
        vocab_image_word = db.query(VocabImageWord).filter(
            VocabImageWord.id == request_data.vocab_image_word_id
        ).first()

        if not vocab_image_word:
            logger.warning(
                f"[add_vocab_image_word] VocabImageWord not found: {request_data.vocab_image_word_id}"
            )
            UserActivityService.log_feature_interaction(
                db=db,
                user_id=current_user.id,
                feature_name="vocab_images",
                interaction_type="word_add_error_invalid_reference",
                details={"vocab_image_word_id": request_data.vocab_image_word_id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vocabulary image word not found"
            )

        word_repo = WordRepository(db)

        # Check if word already exists for this user
        existing_word = word_repo.get_by_main_word(
            user_id=current_user.id,
            main_word=request_data.word
        )

        if existing_word:
            logger.info(
                f"[add_vocab_image_word] Word already exists for user: "
                f"word_id={existing_word.id}, user_id={current_user.id}"
            )
            UserActivityService.log_feature_interaction(
                db=db,
                user_id=current_user.id,
                feature_name="vocab_images",
                interaction_type="word_add_existing",
                details={
                    "word_id": existing_word.id,
                    "vocab_image_word_id": request_data.vocab_image_word_id,
                    "word": request_data.word
                }
            )
            return AddVocabImageWordResponse(
                status="existing",
                message=f"'{request_data.word}' is already in your vocabulary",
                word_id=existing_word.id
            )

        # Create new word with vocab_image_word_id reference
        word_data = {
            "main": request_data.word,
            "meaning": request_data.definition or vocab_image_word.definition,
            "vocab_image_word_id": request_data.vocab_image_word_id
        }
        new_word = word_repo.create(user_id=current_user.id, word_data=word_data)

        # Manually set vocab_image_word_id since create doesn't support it
        from features.words.models import Word
        new_word.vocab_image_word_id = request_data.vocab_image_word_id
        db.add(new_word)
        db.commit()
        db.refresh(new_word)

        logger.info(
            f"[add_vocab_image_word] Word created successfully: "
            f"word_id={new_word.id}, vocab_image_word_id={request_data.vocab_image_word_id}"
        )

        # Log de actividad - éxito
        UserActivityService.log_feature_interaction(
            db=db,
            user_id=current_user.id,
            feature_name="vocab_images",
            interaction_type="word_add_success",
            details={
                "word_id": new_word.id,
                "vocab_image_word_id": request_data.vocab_image_word_id,
                "word": request_data.word
            }
        )

        return AddVocabImageWordResponse(
            status="success",
            message=f"'{request_data.word}' added to your vocabulary!",
            word_id=new_word.id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[add_vocab_image_word] Error: {e}", exc_info=True)
        UserActivityService.log_feature_interaction(
            db=db,
            user_id=current_user.id,
            feature_name="vocab_images",
            interaction_type="word_add_error",
            details={
                "word": request_data.word,
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add word"
        )


@router.get("/", response_model=dict)
@log_endpoint
def list_vocab_images(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all vocabulary image themes with their metadata.
    Does not include words - use GET /vocab-imgs/{vocab_image_id}/words for that.

    Response:
    {
        "items": [
            {
                "id": "wild-west-001",
                "name": "Wild West",
                "description": "Words and expressions from the American Frontier",
                "cover_image": "/west_cover.png",
                "main_image": "/west.png",
                "words_count": 24
            }
        ],
        "total": 1
    }
    """
    logger.info(f"[list_vocab_images] User {current_user.id}: Fetching vocabulary images")

    # Log de actividad
    UserActivityService.log_feature_interaction(
        db=db,
        user_id=current_user.id,
        feature_name="vocab_images",
        interaction_type="list_themes",
        details={}
    )

    try:
        # Get all active vocabulary images
        vocab_images = db.exec(
            select(VocabImage).where(VocabImage.is_active == True)
        ).all()

        items = []
        for img in vocab_images:
            # Count words in this image
            words_count = db.exec(
                select(VocabImageWord).where(
                    VocabImageWord.vocab_image_id == img.id
                )
            ).all()

            items.append({
                "id": img.id,
                "name": img.name,
                "description": img.description,
                "cover_image": img.cover_image,
                "main_image": img.main_image,
                "words_count": len(words_count)
            })

        logger.debug(f"[list_vocab_images] Retrieved {len(items)} vocabulary images")

        return {
            "items": items,
            "total": len(items)
        }

    except Exception as e:
        logger.error(f"[list_vocab_images] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch vocabulary images"
        )


@router.get("/{vocab_image_id}/words", response_model=dict)
@log_endpoint
def list_vocab_image_words(
    vocab_image_id: str = Path(..., description="Vocabulary image ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all words in a vocabulary image theme with their status.
    Checks if each word has been added by the current user.

    Response:
    {
        "items": [
            {
                "id": "west-001",
                "word": "Outlaw",
                "definition": "A criminal who is wanted by law enforcement",
                "category": "People",
                "is_added": false
            },
            {
                "id": "west-002",
                "word": "Sheriff",
                "definition": "The law enforcement officer of a county",
                "category": "People",
                "is_added": true,
                "word_id": 123
            }
        ],
        "total": 24,
        "vocab_image": {
            "id": "wild-west-001",
            "name": "Wild West"
        }
    }
    """
    logger.info(
        f"[list_vocab_image_words] User {current_user.id}: "
        f"Fetching words for vocab_image '{vocab_image_id}'"
    )

    # Log de actividad
    UserActivityService.log_feature_interaction(
        db=db,
        user_id=current_user.id,
        feature_name="vocab_images",
        interaction_type="list_words",
        details={"vocab_image_id": vocab_image_id}
    )

    try:
        # Get vocabulary image
        vocab_image = db.exec(
            select(VocabImage).where(VocabImage.id == vocab_image_id)
        ).first()

        if not vocab_image:
            logger.warning(f"[list_vocab_image_words] VocabImage not found: {vocab_image_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vocabulary image not found"
            )

        # Get all words in this vocabulary image
        vocab_image_words = db.exec(
            select(VocabImageWord)
            .where(VocabImageWord.vocab_image_id == vocab_image_id)
            .order_by(VocabImageWord.word_order)
        ).all()

        # Get all words added by user that have vocab_image_word_id reference
        user_added_word_ids = db.exec(
            select(Word.vocab_image_word_id)
            .where(
                Word.user_id == current_user.id,
                Word.vocab_image_word_id != None,
                Word.is_active == True
            )
        ).all()

        # Create set for faster lookup
        added_vocab_word_ids = set(user_added_word_ids)

        items = []
        for vocab_word in vocab_image_words:
            is_added = vocab_word.id in added_vocab_word_ids

            word_item = {
                "id": vocab_word.id,
                "word": vocab_word.word,
                "definition": vocab_word.definition,
                "category": vocab_word.category,
                "is_added": is_added
            }

            # If word is added, also return the word_id from user's words
            if is_added:
                user_word = db.exec(
                    select(Word).where(
                        Word.user_id == current_user.id,
                        Word.vocab_image_word_id == vocab_word.id,
                        Word.is_active == True
                    )
                ).first()
                if user_word:
                    word_item["word_id"] = user_word.id

            items.append(word_item)

        logger.debug(
            f"[list_vocab_image_words] Retrieved {len(items)} words "
            f"from vocab_image '{vocab_image_id}'"
        )

        return {
            "items": items,
            "total": len(items),
            "vocab_image": {
                "id": vocab_image.id,
                "name": vocab_image.name
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[list_vocab_image_words] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch vocabulary image words"
        )

# backend/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlmodel import Session, select
from db import get_db
from auth.models import User
from features.words.models import Word, WordStatistics
from features.examples.models import Example, ExampleType
from core.learning_path.models import LearningState
from core.enums import ContentType
from auth.repository import hash_password, verify_password, create_access_token
from pydantic import BaseModel, EmailStr
from logging_client import logger
from decorators import log_endpoint
from pathlib import Path
from features.examples.helpers import approximate_text_form
from config import QuotaValidator

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    """Modelo para login con JSON"""
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str


def assign_default_words(user_id: int, db: Session):
    """Assign default words from seed_user_words.py to new user"""
    try:
        import json
        from core.learning_path.models import LearningPathQueue
        from core.learning_path.enums import LearningPathQueueStatus

        seed_file = Path(__file__).parent.parent / "seeds" / "seed_user_words.py"

        if not seed_file.exists():
            logger.warning(f"Seed file not found: {seed_file}")
            return

        with open(seed_file, 'r', encoding='utf-8') as f:
            content = f.read()
            words_data = json.loads(content)

        # Reverse the order so last word in seed is created first
        for word_data in reversed(words_data):
            word = Word(
                main=word_data.get("main"),
                meaning=word_data.get("meaning"),
                synonyms=word_data.get("synonyms"),
                type=word_data.get("type"),
                frequency=word_data.get("frequency"),
                level=word_data.get("level", 1),
                context=word_data.get("context"),
                source_text=word_data.get("source_text"),
                explanation=word_data.get("explanation"),
                user_id=user_id
            )
            db.add(word)
            db.flush()  # Flush to get the word ID

            # Create WordStatistics for this word (NEW state, both content types)
            for content_type in [ContentType.EXAMPLE, ContentType.BEST_OPTIONS]:
                word_stats = WordStatistics(
                    word_id=word.id,
                    type=content_type,
                    learning_state=LearningState.NEW,
                    times_seen=0,
                    current_cycle_seen=0
                )
                db.add(word_stats)

            # Create examples for this word and add to learning path queue
            examples_list = word_data.get("examples", [])

            for idx, example_text in enumerate(examples_list):
                # First 3 are INITIAL, rest are EXPLORE
                example_type = ExampleType.INITIAL if idx < 3 else ExampleType.EXPLORE

                # Get text_form
                text_form = approximate_text_form(example_text, word.main)

                example = Example(
                    type=example_type,
                    text=example_text,
                    text_form=text_form,
                    word_id=word.id
                )
                db.add(example)
                db.flush()  # Flush to get example ID

                # Add example to learning path queue for EXAMPLE content type
                queue_item = LearningPathQueue(
                    content_id=example.id,
                    content_type=ContentType.EXAMPLE,
                    word_id=word.id,
                    user_id=user_id,
                    status=LearningPathQueueStatus.PENDING,
                    priority=0.0
                )
                db.add(queue_item)
                logger.debug(
                    f"[assign_default_words] Added example {example.id} (word {word.id}) "
                    f"to learning path queue for user {user_id}"
                )

        db.commit()
        logger.info(f"Default words, examples and learning path queue items assigned to user {user_id}")
    except Exception as e:
        logger.error(f"Error assigning default words to user {user_id}: {e}", exc_info=True)
        db.rollback()
        # Don't raise exception, continue with user creation


@router.post("/register", status_code=status.HTTP_201_CREATED)
@log_endpoint
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    logger.info(f"User registration attempt: {user_data.email}")

    # Validar que no se haya alcanzado el máximo de usuarios
    QuotaValidator.validate_max_users(db)

    # Verificar si ya existe el correo
    existing_user = db.exec(select(User).where(User.email == user_data.email)).first()
    if existing_user:
        logger.warning(f"Registration failed - email already exists: {user_data.email}")
        raise HTTPException(status_code=400, detail="Email is already registered")

    hashed = hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Assign default words to new user
    assign_default_words(new_user.id, db)

    logger.info(f"User registered successfully: {user_data.email} (ID: {new_user.id})")
    return {"message": "Account created successfully", "user_id": new_user.id}

@router.post("/login", response_model=Token)
@log_endpoint
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint de login que acepta JSON.

    Body:
    {
      "email": "user@example.com",
      "password": "password123"
    }
    """
    logger.info(f"Login attempt: {credentials.email}")
    user = db.exec(select(User).where(User.email == credentials.email)).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning(f"Login failed for email: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    logger.info(f"User logged in successfully: {credentials.email}")
    return {"access_token": access_token, "token_type": "bearer"}
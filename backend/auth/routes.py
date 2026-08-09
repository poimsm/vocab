# backend/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlmodel import Session, select
from db import get_db
from models import User
from auth.repository import hash_password, verify_password, create_access_token
from pydantic import BaseModel, EmailStr
from logging_client import logger
from decorators import log_endpoint

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

@router.post("/register", status_code=status.HTTP_201_CREATED)
@log_endpoint
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    logger.info(f"User registration attempt: {user_data.email}")
    # Verificar si ya existe el correo
    existing_user = db.exec(select(User).where(User.email == user_data.email)).first()
    if existing_user:
        logger.warning(f"Registration failed - email already exists: {user_data.email}")
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    hashed = hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"User registered successfully: {user_data.email} (ID: {new_user.id})")
    return {"message": "Usuario creado con éxito", "user_id": new_user.id}

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
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    logger.info(f"User logged in successfully: {credentials.email}")
    return {"access_token": access_token, "token_type": "bearer"}
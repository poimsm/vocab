import sys
import os
from sqlmodel import Session, select
from db import engine
from models import User
from auth import hash_password
from logging_config import logger 

PASS_ADMIN = os.getenv("PASS_ADMIN_USER")

def seed_users():
    logger.info("Loading initial users...")

    raw_users = [
        {
            "username": "admin",
            "email": "admin@example.com",
            "password": PASS_ADMIN,
            "is_admin": True
        },
        {
            "username": "user1",
            "email": "user1@example.com",
            "password": "password",
            "is_admin": False
        }
    ]

    with Session(engine) as db:
        try:
            for user_data in raw_users:
                # 1. Verificamos si el usuario ya existe por su email o username
                statement = select(User).where(User.email == user_data["email"])
                existing_user = db.exec(statement).first()

                if existing_user:
                    logger.warning(f"User {user_data['username']} ({user_data['email']}) already exists. Skipping...")
                    continue

                # 2. Creamos la instancia hasheando la contraseña antes de guardarla
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    hashed_password=hash_password(user_data["password"]),
                    is_admin=user_data["is_admin"]
                )

                db.add(new_user)
                logger.info(f"Preparing user: {user_data['username']} ({'Admin' if user_data['is_admin'] else 'Normal'})")

            db.commit()
            logger.info("Users loaded successfully.")

        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error loading users: {e}")
            sys.exit(1)

if __name__ == "__main__":
    seed_users()
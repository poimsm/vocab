import sys
import os
from sqlmodel import Session, select
from db import engine
from models import User
from auth import hash_password 

PASS_ADMIN = os.getenv("PASS_ADMIN_USER")

def seed_users():
    print("Cargando usuarios iniciales...")
    
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
                    print(f"⚠️ El usuario {user_data['username']} ({user_data['email']}) ya existe. Saltando...")
                    continue
                
                # 2. Creamos la instancia hasheando la contraseña antes de guardarla
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    hashed_password=hash_password(user_data["password"]),
                    is_admin=user_data["is_admin"]
                )
                
                db.add(new_user)
                print(f"➕ Preparando usuario: {user_data['username']} ({'Admin' if user_data['is_admin'] else 'Normal'})")
            
            db.commit()
            print("✅ Usuarios cargados con exito.")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Error inesperado al cargar usuarios: {e}")
            sys.exit(1)

if __name__ == "__main__":
    seed_users()
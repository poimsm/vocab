"""
Servicio abstracto para manejo de SSE (Server-Sent Events).

Proporciona una interfaz genérica para:
- Crear streams SSE
- Autenticación para SSE
- Manejo de conexiones Redis para pubsub
"""

import json
import time
import asyncio
import redis
import os
from typing import Optional, Callable
from fastapi import HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from auth.models import User
from auth.repository import get_current_user, SECRET_KEY, ALGORITHM
from logging_client import logger
import jwt
from jwt import PyJWTError
from db import get_db


async def get_current_user_sse(
    db: Session = Depends(get_db),
    token: Optional[str] = None,
) -> User:
    """
    Autenticación para SSE endpoint.
    Intenta obtener el usuario del token en query param (para SSE que no soporta headers)
    o usa la autenticación estándar.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Si hay token en query param, usarlo
    if token:
        logger.debug(f"[SSE Auth] Attempting to authenticate via query token")
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM]
            )
            email: str = payload.get("sub")
            if email is None:
                logger.warning("[SSE Auth] Token validation failed: no email in payload")
                raise credentials_exception

            user = db.exec(
                select(User).where(User.email == email)
            ).first()

            if user is None:
                logger.warning(f"[SSE Auth] User not found for email: {email}")
                raise credentials_exception

            logger.debug(f"[SSE Auth] User authenticated via query token: {user.id} ({email})")
            return user

        except PyJWTError as e:
            logger.warning(f"[SSE Auth] JWT validation error: {str(e)}")
            raise credentials_exception
        except Exception as e:
            logger.error(f"[SSE Auth] Unexpected error: {str(e)}", exc_info=True)
            raise credentials_exception

    # Si no hay token en query param, usar autenticación estándar (header)
    logger.debug("[SSE Auth] No query token, falling back to standard auth")
    return get_current_user(token=None, db=db)


class SSEStreamService:
    """
    Servicio genérico para crear SSE streams.

    Maneja:
    - Conexión a Redis
    - Subscripción a canales de patrones
    - Generación de eventos SSE
    - Keep-alive y manejo de desconexiones
    """

    def __init__(
        self,
        user_id: int,
        channel_pattern: str,
        logger_name: str = "SSEStreamService",
    ):
        """
        Args:
            user_id: ID del usuario para filtrar eventos
            channel_pattern: Patrón de canal Redis (ej: "user:123:examples_explore.*")
            logger_name: Nombre para logs (ej: "[explore_examples_stream]")
        """
        self.user_id = user_id
        self.channel_pattern = channel_pattern
        self.logger_name = logger_name
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))

    def get_stream_response(self) -> StreamingResponse:
        """Retorna un StreamingResponse con el SSE stream."""
        try:
            r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=2,
            )
            pubsub = r.pubsub()
            pubsub.psubscribe(self.channel_pattern)
            logger.info(
                f"{self.logger_name} Suscrito a eventos de user {self.user_id} "
                f"(patrón: {self.channel_pattern})"
            )
        except Exception as e:
            logger.error(f"{self.logger_name} Redis connection error: {e}")
            return StreamingResponse(
                iter([f"event: error\ndata: {json.dumps({'error': 'Redis connection failed'})}\n\n"]),
                media_type="text/event-stream",
                status_code=500
            )

        async def event_generator():
            """Genera eventos SSE usando Redis pubsub"""
            try:
                logger.debug(f"{self.logger_name} Event generator iniciado")
                last_keep_alive = time.time()

                while True:
                    try:
                        # Usar get_message() no-bloqueante
                        message = pubsub.get_message()

                        if message and message.get("type") in ("message", "pmessage"):
                            channel = message.get("channel")
                            raw_data = message.get("data")

                            if channel and raw_data:
                                try:
                                    data = json.loads(raw_data)
                                    event_type = channel.split(":")[-1]
                                    yield f"event: {event_type}\n"
                                    yield f"data: {json.dumps(data)}\n\n"
                                    logger.debug(
                                        f"{self.logger_name} Evento enviado: {event_type}"
                                    )
                                    last_keep_alive = time.time()
                                except json.JSONDecodeError:
                                    logger.error(f"{self.logger_name} Invalid JSON: {raw_data}")
                        else:
                            # Keep-alive cada 30 segundos sin eventos
                            now = time.time()
                            if now - last_keep_alive > 30:
                                yield ": keep-alive\n\n"
                                last_keep_alive = now
                            else:
                                # Pequeña pausa para no consumir CPU
                                await asyncio.sleep(0.2)

                    except Exception as e:
                        logger.error(f"{self.logger_name} Error en generador: {e}")
                        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                        break

            except GeneratorExit:
                logger.debug(f"{self.logger_name} Cliente desconectado")
            finally:
                try:
                    pubsub.close()
                except:
                    pass

        return StreamingResponse(event_generator(), media_type="text/event-stream")

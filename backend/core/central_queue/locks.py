import asyncio
from datetime import datetime, timezone, timedelta
from sqlmodel import Session
from core.central_queue.models import CentralLockState, CentralStateEnum


class DistributedLock:
    def __init__(self, engine, lock_type: str, ttl_seconds: int = 30, heartbeat_interval: int = 10):
        self.engine = engine
        self.lock_type = lock_type
        self.ttl_seconds = ttl_seconds
        self.heartbeat_interval = heartbeat_interval
        self._ensure_state_record_exists()

    def _ensure_state_record_exists(self):
        with Session(self.engine) as session:
            state_record = session.get(CentralLockState, self.lock_type)
            if not state_record:
                state_record = CentralLockState(
                    lock_type=self.lock_type,
                    state=CentralStateEnum.IDLE,
                    expires_at=None
                )
                session.add(state_record)
                session.commit()

    def try_acquire(self) -> bool:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            state_record = session.get(CentralLockState, self.lock_type)

            if state_record.state == CentralStateEnum.BUSY:
                if state_record.expires_at and state_record.expires_at > now:
                    return False  # Sigue ocupado

            state_record.state = CentralStateEnum.BUSY
            state_record.expires_at = now + timedelta(seconds=self.ttl_seconds)
            session.add(state_record)
            session.commit()
            return True

    async def heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                now = datetime.now(timezone.utc)
                with Session(self.engine) as session:
                    state_record = session.get(
                        CentralLockState, self.lock_type)
                    if state_record and state_record.state == CentralStateEnum.BUSY:
                        state_record.expires_at = now + \
                            timedelta(seconds=self.ttl_seconds)
                        session.add(state_record)
                        session.commit()
        except asyncio.CancelledError:
            pass

    def release(self):
        with Session(self.engine) as session:
            state_record = session.get(CentralLockState, self.lock_type)
            if state_record:
                state_record.state = CentralStateEnum.IDLE
                state_record.expires_at = None
                session.add(state_record)
                session.commit()

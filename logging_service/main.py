from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import os
from typing import List

app = FastAPI(title="Logging Service")

LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
LOG_DIR.mkdir(exist_ok=True, parents=True)
LOG_FILE = LOG_DIR / "centralized.log"


class LogEntry(BaseModel):
    level: str
    message: str
    source: str = "unknown"  # FastAPI, Celery, etc.


class LogResponse(BaseModel):
    timestamp: str
    level: str
    message: str
    source: str


@app.post("/logs")
async def receive_log(entry: LogEntry):
    """Recibe un log y lo guarda en archivo"""
    timestamp = datetime.now().isoformat()
    log_line = f"{timestamp} - {entry.level.upper()} - [{entry.source}] - {entry.message}\n"

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
        return {"status": "ok", "timestamp": timestamp}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs", response_model=List[LogResponse])
async def get_logs(limit: int = 100, level: str = None):
    """Obtiene los últimos logs"""
    try:
        if not LOG_FILE.exists():
            return []

        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        logs = []
        for line in lines[-limit:]:
            try:
                # Parsear formato: "timestamp - LEVEL - [source] - message"
                parts = line.strip().split(" - ", 3)
                if len(parts) >= 4:
                    timestamp = parts[0]
                    log_level = parts[1]
                    source = parts[2].strip("[]")
                    message = parts[3]

                    if level is None or log_level == level.upper():
                        logs.append(
                            LogResponse(
                                timestamp=timestamp,
                                level=log_level,
                                message=message,
                                source=source,
                            )
                        )
            except Exception:
                continue

        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/download")
async def download_logs():
    """Descarga el archivo de logs completo"""
    if not LOG_FILE.exists():
        raise HTTPException(status_code=404, detail="No logs found")
    return {"file": LOG_FILE.read_text()}


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "service": "logging"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

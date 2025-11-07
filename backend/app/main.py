from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket

from app.api.routes import auth, parts, legacy
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(parts.router)
app.include_router(legacy.router)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

@app.websocket("/realtime")
async def realtime(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"message": "Realtime channel established"})
    await websocket.close()

"""Gateway service entrypoint -- auth-only, not a data-plane proxy.

See docs/api/gateway.md and docs/adr/ADR-007-multiuser-pivot.md.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from core.config import get_settings
from services.gateway.routes import router as auth_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Gateway Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Required by authlib's Starlette OAuth client to persist the CSRF `state`
# param between the /login redirect and the /callback round-trip.
app.add_middleware(SessionMiddleware, secret_key=get_settings().jwt_secret)

app.include_router(auth_router)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "gateway"}

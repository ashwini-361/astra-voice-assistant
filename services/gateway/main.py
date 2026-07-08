"""Gateway service entrypoint.

PR1A: skeleton + health check only. OAuth/JWT routes land in PR1B
(services/gateway/oauth.py, jwt_utils.py, routes.py) -- see
docs/api/gateway.md and docs/adr/ADR-007-multiuser-pivot.md.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "gateway"}

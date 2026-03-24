from fastapi import APIRouter
from gateway.core.observability import is_tracing_enabled

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "tracing": is_tracing_enabled(),
    }

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_health_service
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health")
def health(service: HealthService = Depends(get_health_service)) -> JSONResponse:
    result = service.check()
    return JSONResponse(status_code=200 if result["database"] == "ok" else 503, content=result)

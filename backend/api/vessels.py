from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ais.models import HealthResponse, SearchResult, Vessel

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    app = request.app
    return HealthResponse(
        status="ok",
        ais_configured=app.state.ais_client.configured,
        ais_connected=app.state.ais_client.connected,
        tracked_vessels=await app.state.store.count(),
    )


@router.get("/vessels/search", response_model=SearchResult)
async def search_vessels(request: Request, q: str = Query("", min_length=1, max_length=80)) -> SearchResult:
    vessels = await request.app.state.store.search(q)
    return SearchResult(vessels=vessels, query=q)


@router.get("/vessels/{mmsi}", response_model=Vessel)
async def get_vessel(mmsi: int, request: Request) -> Vessel | JSONResponse:
    vessel = await request.app.state.store.get(mmsi)
    if vessel is None:
        return JSONResponse({"detail": "Vessel not found"}, status_code=404)
    return vessel

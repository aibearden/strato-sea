from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ais.client import AISStreamClient
from ais.models import ClientPingMessage, ClientViewportMessage, ErrorMessage, PongMessage, Viewport
from ais.subscription import SubscriptionManager
from api.vessels import router as vessels_router
from config import get_settings
from services.hub import ClientHub
from services.vessel_store import VesselStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("strato-sea")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = VesselStore(
        ttl_seconds=settings.vessel_ttl_seconds,
        sweep_interval=settings.stale_sweep_interval_seconds,
    )

    async def on_ais_message(envelope: dict) -> None:
        await store.ingest(envelope)

    ais_client = AISStreamClient(
        url=settings.aisstream_url,
        api_key=settings.aisstream_api_key,
        on_message=on_ais_message,
    )

    subscription = SubscriptionManager(
        min_interval_seconds=settings.subscription_min_interval_seconds,
        on_boxes=ais_client.set_bounding_boxes,
    )
    hub = ClientHub(
        store,
        subscription,
        buffer_ratio=settings.viewport_buffer_ratio,
        min_zoom=settings.min_zoom_for_stream,
        max_span_deg=settings.max_viewport_span_deg,
        broadcast_interval=settings.broadcast_interval_seconds,
    )
    ais_client.set_state_handler(hub.set_ais_connected)

    app.state.settings = settings
    app.state.store = store
    app.state.hub = hub
    app.state.ais_client = ais_client
    app.state.subscription = subscription

    tasks = [
        asyncio.create_task(ais_client.run(), name="ais-client"),
        asyncio.create_task(subscription.run(), name="ais-subscription"),
        asyncio.create_task(store.sweep_loop(), name="vessel-sweep"),
        asyncio.create_task(hub.flush_loop(), name="client-flush"),
    ]
    logger.info("Strato Sea backend started")
    try:
        yield
    finally:
        await ais_client.stop()
        await subscription.stop()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Strato Sea backend stopped")


app = FastAPI(title="Strato Sea", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(vessels_router)


@app.websocket("/ws/ais")
async def ais_socket(websocket: WebSocket) -> None:
    hub: ClientHub = websocket.app.state.hub
    session = await hub.connect(websocket)
    sender = asyncio.create_task(hub.sender_loop(session))
    try:
        while True:
            raw = await websocket.receive_json()
            message_type = raw.get("type") if isinstance(raw, dict) else None
            if message_type == "ping":
                ClientPingMessage.model_validate(raw)
                await hub.enqueue(session, PongMessage().model_dump())
                continue
            if message_type == "viewport":
                parsed = ClientViewportMessage.model_validate(raw)
                viewport = Viewport(
                    west=parsed.west,
                    south=parsed.south,
                    east=parsed.east,
                    north=parsed.north,
                    zoom=parsed.zoom,
                )
                await hub.set_viewport(session, viewport)
                continue
            await hub.enqueue(
                session,
                ErrorMessage(message="Unknown message type").model_dump(),
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket client error")
    finally:
        sender.cancel()
        await hub.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )

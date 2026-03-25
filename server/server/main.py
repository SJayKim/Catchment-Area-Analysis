"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.routes.chat import router as chat_router
from server.api.routes.districts import router as districts_router
from server.api.routes.map_data import router as map_data_router

app = FastAPI(
    title="MarketScope AI",
    description="상권분석 AI 서비스 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(districts_router)
app.include_router(map_data_router)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

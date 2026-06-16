from fastapi import FastAPI

from app.api.draft import router as draft_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Hidden Name Draft API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(draft_router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "hidden-name-draft"}

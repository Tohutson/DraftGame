from fastapi import FastAPI

from api.draft import router as draft_router

app = FastAPI(
    title="NFL Draft Simulator API",
    version="1.0.0",
)

# Register routers
app.include_router(draft_router)


@app.get("/")
def health_check():
    return {"status": "ok"}

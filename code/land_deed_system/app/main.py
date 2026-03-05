from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router

app = FastAPI(
    title="Ancient Land Deed Analysis System",
    description="A high-precision system for parsing, translating, and normalizing ancient Chinese land deeds using Prompt Engineering and NLP.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router, prefix="/api/v1")

@app.get("/")
async def root():
    return FileResponse('app/static/index.html')

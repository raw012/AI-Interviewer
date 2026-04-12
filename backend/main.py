"""FastAPI application entry point for AI Interview Coach."""

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Import routers
from routers.auth_router import router as auth_router
from routers.interview_router import router as interview_router
from routers.user_router import router as user_router

# Import database
from database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("Initializing database...")
    await init_db()
    yield
    # Shutdown
    print("Closing database...")
    await close_db()


app = FastAPI(title="AI Interview Coach", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(interview_router)
app.include_router(user_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

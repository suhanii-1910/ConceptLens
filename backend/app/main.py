"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.courses import router as courses_router
from app.api.sources import router as sources_router
from app.api.endpoints.retrieval import router as retrieval_router
from app.api.endpoints.ask import router as ask_router
from app.api.endpoints.assessment import router as assessment_router
from app.api.endpoints.mastery import router as mastery_router
from app.api.endpoints.reasoning_diagnosis import router as reasoning_diagnosis_router

from app.api.endpoints.adaptive_learning import router as adaptive_learning_router

app = FastAPI(
    title="ConceptLens",
    description="Multimodal adaptive-learning platform — backend API",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(courses_router)
app.include_router(sources_router)
app.include_router(retrieval_router)
app.include_router(ask_router)
app.include_router(assessment_router)
app.include_router(mastery_router)
app.include_router(reasoning_diagnosis_router)

app.include_router(adaptive_learning_router)

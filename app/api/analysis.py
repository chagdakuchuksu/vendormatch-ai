from fastapi import APIRouter

from app.api.deps import Analysis
from app.schemas.analysis import ProjectAnalysis, ProjectComparison

router = APIRouter(prefix="/api/projects", tags=["analysis"])


@router.get("/{project_id}/analysis", response_model=ProjectAnalysis)
def get_analysis(project_id: int, analysis: Analysis) -> ProjectAnalysis:
    """Full, explainable analysis of every vendor, computed from the current stored data."""
    return analysis.analyze(project_id)


@router.get("/{project_id}/comparison", response_model=ProjectComparison)
def get_comparison(project_id: int, analysis: Analysis) -> ProjectComparison:
    """One row per vendor for the comparison table, computed from the current stored data."""
    return analysis.compare(project_id)

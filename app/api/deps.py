"""FastAPI dependencies. App-wide objects live on `app.state` (set in create_app)."""

import sqlite3
from typing import Annotated, Iterator

from fastapi import Depends, Request

from app.config import ScoringConfig, Settings
from app.services.analysis_service import AnalysisService
from app.services.demo_service import DemoService
from app.services.project_service import ProjectService
from app.services.scoring.engine import SemanticScorer
from app.services.vendor_service import VendorService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_scoring_config(request: Request) -> ScoringConfig:
    return request.app.state.scoring_config


def get_semantic_scorer(request: Request) -> SemanticScorer:
    return request.app.state.semantic_scorer


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    conn = request.app.state.database.connect()
    try:
        yield conn
    finally:
        conn.close()


Connection = Annotated[sqlite3.Connection, Depends(get_connection)]
Config = Annotated[ScoringConfig, Depends(get_scoring_config)]


def get_project_service(conn: Connection, config: Config) -> ProjectService:
    return ProjectService(conn, config)


def get_vendor_service(conn: Connection) -> VendorService:
    return VendorService(conn)


def get_analysis_service(
    conn: Connection, config: Config, scorer: Annotated[SemanticScorer, Depends(get_semantic_scorer)]
) -> AnalysisService:
    return AnalysisService(conn, scorer, config)


def get_demo_service(
    conn: Connection, config: Config, settings: Annotated[Settings, Depends(get_settings)]
) -> DemoService:
    return DemoService(conn, settings, config)


Projects = Annotated[ProjectService, Depends(get_project_service)]
Vendors = Annotated[VendorService, Depends(get_vendor_service)]
Analysis = Annotated[AnalysisService, Depends(get_analysis_service)]
Demo = Annotated[DemoService, Depends(get_demo_service)]

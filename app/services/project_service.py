import sqlite3

from app.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from app.data.repositories import ProjectRepository
from app.errors import NotFoundError
from app.schemas.project import Project, ProjectCreate, ProjectSummary
from app.services.criteria_builder import build_criteria


class ProjectService:
    """Project workflow: criteria are (re)materialized and validated on every create/update."""

    def __init__(self, conn: sqlite3.Connection, config: ScoringConfig = DEFAULT_SCORING_CONFIG):
        self.conn = conn
        self.config = config
        self.projects = ProjectRepository(conn)

    def create(self, data: ProjectCreate) -> Project:
        criteria = build_criteria(data, self.config)
        with self.conn:
            project_id = self.projects.create(data, criteria)
        return self.get(project_id)

    def get(self, project_id: int) -> Project:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError(f"Project {project_id} not found.", {"project_id": project_id})
        return project

    def list(self) -> list[ProjectSummary]:
        return self.projects.list_summaries()

    def update(self, project_id: int, data: ProjectCreate) -> Project:
        if not self.projects.exists(project_id):
            raise NotFoundError(f"Project {project_id} not found.", {"project_id": project_id})
        criteria = build_criteria(data, self.config)
        with self.conn:
            self.projects.update(project_id, data, criteria)
        return self.get(project_id)

    def delete(self, project_id: int) -> None:
        with self.conn:
            if not self.projects.delete(project_id):
                raise NotFoundError(f"Project {project_id} not found.", {"project_id": project_id})

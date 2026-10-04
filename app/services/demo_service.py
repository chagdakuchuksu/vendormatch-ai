"""Load the fictional demo project and vendors from examples/.

Each call creates a fresh, identical copy (so concurrent demo users never edit each other's
data) and prunes the oldest demo copies beyond `Settings.max_demo_projects`.
"""

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from app.config import DEFAULT_SCORING_CONFIG, ScoringConfig, Settings
from app.data.repositories import ProjectRepository, VendorRepository
from app.schemas.project import ProjectCreate
from app.schemas.vendor import VendorCreate
from app.services.criteria_builder import build_criteria

PROJECT_FILE = "demo_project.json"
VENDORS_FILE = "demo_vendors.json"


class DemoData(BaseModel):
    project: ProjectCreate
    vendors: list[VendorCreate]
    profiles: dict[str, str] = {}  # vendor name -> one-line description of the intended profile


class DemoLoadResult(BaseModel):
    project_id: int
    vendor_ids: list[int]
    vendor_profiles: dict[str, str]
    fictional: bool = True
    notice: str
    pruned_project_ids: list[int]


def read_demo_data(examples_dir: Path) -> DemoData:
    project_doc = json.loads((examples_dir / PROJECT_FILE).read_text(encoding="utf-8"))
    vendors_doc = json.loads((examples_dir / VENDORS_FILE).read_text(encoding="utf-8"))
    return DemoData(
        project=project_doc["project"], vendors=vendors_doc["vendors"], profiles=vendors_doc.get("profiles", {})
    )


class DemoService:
    def __init__(self, conn: sqlite3.Connection, settings: Settings, config: ScoringConfig = DEFAULT_SCORING_CONFIG):
        self.conn = conn
        self.settings = settings
        self.config = config

    def load(self) -> DemoLoadResult:
        demo = read_demo_data(self.settings.examples_dir)
        criteria = build_criteria(demo.project, self.config)
        projects, vendors = ProjectRepository(self.conn), VendorRepository(self.conn)

        with self.conn:  # one transaction: project, vendors and pruning
            project_id = projects.create(demo.project, criteria, is_demo=True)
            vendor_ids = [vendors.create(project_id, v, is_demo=True) for v in demo.vendors]
            stale = projects.demo_project_ids()[self.settings.max_demo_projects :]
            for old_id in stale:
                projects.delete(old_id)

        return DemoLoadResult(
            project_id=project_id,
            vendor_ids=vendor_ids,
            vendor_profiles=demo.profiles,
            notice="All demo companies, people and data are fictional.",
            pruned_project_ids=stale,
        )

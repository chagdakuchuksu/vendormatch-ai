"""Persistence only: SQL in, Pydantic models out. No validation rules, no scoring.

Repositories never commit; services own transactions (`with conn:`).
"""

import json
import sqlite3
from datetime import datetime, timezone

from app.schemas.criterion import Criterion
from app.schemas.project import Project, ProjectCreate, ProjectSummary
from app.schemas.vendor import Vendor, VendorCreate

_PROJECT_DATA_FIELDS = set(ProjectCreate.model_fields)
_VENDOR_DATA_FIELDS = set(VendorCreate.model_fields)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, data: ProjectCreate, criteria: list[Criterion], *, is_demo: bool = False) -> int:
        now = _now()
        cur = self.conn.execute(
            "INSERT INTO projects (name, data, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (data.name, self._serialize(data, criteria), int(is_demo), now, now),
        )
        return cur.lastrowid

    def update(self, project_id: int, data: ProjectCreate, criteria: list[Criterion]) -> bool:
        cur = self.conn.execute(
            "UPDATE projects SET name = ?, data = ?, updated_at = ? WHERE id = ?",
            (data.name, self._serialize(data, criteria), _now(), project_id),
        )
        return cur.rowcount == 1

    def get(self, project_id: int) -> Project | None:
        row = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._to_model(row) if row else None

    def exists(self, project_id: int) -> bool:
        return self.conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is not None

    def list_summaries(self) -> list[ProjectSummary]:
        rows = self.conn.execute(
            """
            SELECT p.id, p.name, p.is_demo, p.data, p.created_at, p.updated_at,
                   (SELECT COUNT(*) FROM vendors v WHERE v.project_id = p.id) AS vendor_count
            FROM projects p
            ORDER BY p.created_at DESC, p.id DESC
            """
        ).fetchall()
        return [
            ProjectSummary(
                id=r["id"],
                name=r["name"],
                is_demo=bool(r["is_demo"]),
                vendor_count=r["vendor_count"],
                criteria_count=len(json.loads(r["data"])["criteria"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def delete(self, project_id: int) -> bool:
        return self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,)).rowcount == 1

    def demo_project_ids(self) -> list[int]:
        """Newest first."""
        rows = self.conn.execute("SELECT id FROM projects WHERE is_demo = 1 ORDER BY id DESC").fetchall()
        return [r["id"] for r in rows]

    @staticmethod
    def _serialize(data: ProjectCreate, criteria: list[Criterion]) -> str:
        doc = data.model_dump(mode="json", include=_PROJECT_DATA_FIELDS - {"criteria"})
        doc["criteria"] = [c.model_dump(mode="json") for c in criteria]
        return json.dumps(doc, ensure_ascii=False)

    @staticmethod
    def _to_model(row: sqlite3.Row) -> Project:
        return Project(
            **json.loads(row["data"]),
            id=row["id"],
            is_demo=bool(row["is_demo"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class VendorRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, project_id: int, data: VendorCreate, *, is_demo: bool = False) -> int:
        now = _now()
        cur = self.conn.execute(
            "INSERT INTO vendors (project_id, name, data, is_demo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, data.name, self._serialize(data), int(is_demo), now, now),
        )
        return cur.lastrowid

    def update(self, vendor_id: int, data: VendorCreate) -> bool:
        cur = self.conn.execute(
            "UPDATE vendors SET name = ?, data = ?, updated_at = ? WHERE id = ?",
            (data.name, self._serialize(data), _now(), vendor_id),
        )
        return cur.rowcount == 1

    def get(self, vendor_id: int) -> Vendor | None:
        row = self.conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        return self._to_model(row) if row else None

    def list_for_project(self, project_id: int) -> list[Vendor]:
        rows = self.conn.execute("SELECT * FROM vendors WHERE project_id = ? ORDER BY id", (project_id,)).fetchall()
        return [self._to_model(r) for r in rows]

    def delete(self, vendor_id: int) -> bool:
        return self.conn.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,)).rowcount == 1

    @staticmethod
    def _serialize(data: VendorCreate) -> str:
        return json.dumps(data.model_dump(mode="json", include=_VENDOR_DATA_FIELDS), ensure_ascii=False)

    @staticmethod
    def _to_model(row: sqlite3.Row) -> Vendor:
        return Vendor(
            **json.loads(row["data"]),
            id=row["id"],
            project_id=row["project_id"],
            is_demo=bool(row["is_demo"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

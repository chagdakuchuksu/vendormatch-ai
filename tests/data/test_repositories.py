"""Repository tests against a temporary SQLite file."""

import pytest

from app.data.database import Database
from app.data.repositories import ProjectRepository, VendorRepository
from app.services.criteria_builder import build_criteria
from tests.helpers import spec_example_project, vendor


@pytest.fixture
def conn(tmp_path):
    db = Database(tmp_path / "repo.db")
    db.init_schema()
    c = db.connect()
    yield c
    c.close()


def test_project_round_trip_preserves_every_field(conn):
    data = spec_example_project()
    criteria = build_criteria(data)
    repo = ProjectRepository(conn)
    pid = repo.create(data, criteria)
    stored = repo.get(pid)
    assert stored.model_dump(include=set(type(data).model_fields) - {"criteria"}) == data.model_dump(exclude={"criteria"})
    assert stored.criteria == criteria


def test_vendor_round_trip_preserves_every_field(conn):
    pid = ProjectRepository(conn).create(spec_example_project(), build_criteria(spec_example_project()))
    v = vendor(name="V", proposed_budget=1.5, proposed_duration=26, duration_unit="weeks", years_experience=0,
               technologies=["Go", "C#"], proposal_text="Ünïcödé text. Second.", previous_projects=["a", "b"])
    repo = VendorRepository(conn)
    stored = repo.get(repo.create(pid, v, is_demo=True))
    assert stored.model_dump(include=set(type(v).model_fields)) == v.model_dump()
    assert stored.is_demo is True and stored.project_id == pid


def test_foreign_keys_cascade(conn):
    projects, vendors = ProjectRepository(conn), VendorRepository(conn)
    pid = projects.create(spec_example_project(), build_criteria(spec_example_project()))
    vid = vendors.create(pid, vendor())
    projects.delete(pid)
    assert vendors.get(vid) is None


def test_missing_rows(conn):
    assert ProjectRepository(conn).get(1) is None
    assert VendorRepository(conn).get(1) is None
    assert ProjectRepository(conn).delete(1) is False
    assert VendorRepository(conn).update(1, vendor()) is False


def test_schema_init_is_idempotent(tmp_path):
    db = Database(tmp_path / "nested" / "dir" / "x.db")
    db.init_schema()
    db.init_schema()
    assert db.path.exists()

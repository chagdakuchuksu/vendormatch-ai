import sqlite3

from app.data.repositories import ProjectRepository, VendorRepository
from app.errors import NotFoundError
from app.schemas.vendor import Vendor, VendorCreate


class VendorService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.projects = ProjectRepository(conn)
        self.vendors = VendorRepository(conn)

    def create(self, project_id: int, data: VendorCreate) -> Vendor:
        self._require_project(project_id)
        with self.conn:
            vendor_id = self.vendors.create(project_id, data)
        return self.get(vendor_id)

    def get(self, vendor_id: int) -> Vendor:
        vendor = self.vendors.get(vendor_id)
        if vendor is None:
            raise NotFoundError(f"Vendor {vendor_id} not found.", {"vendor_id": vendor_id})
        return vendor

    def list(self, project_id: int) -> list[Vendor]:
        self._require_project(project_id)
        return self.vendors.list_for_project(project_id)

    def update(self, vendor_id: int, data: VendorCreate) -> Vendor:
        with self.conn:
            if not self.vendors.update(vendor_id, data):
                raise NotFoundError(f"Vendor {vendor_id} not found.", {"vendor_id": vendor_id})
        return self.get(vendor_id)

    def delete(self, vendor_id: int) -> None:
        with self.conn:
            if not self.vendors.delete(vendor_id):
                raise NotFoundError(f"Vendor {vendor_id} not found.", {"vendor_id": vendor_id})

    def _require_project(self, project_id: int) -> None:
        if not self.projects.exists(project_id):
            raise NotFoundError(f"Project {project_id} not found.", {"project_id": project_id})

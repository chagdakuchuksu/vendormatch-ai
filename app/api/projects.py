from fastapi import APIRouter, Response, status

from app.api.deps import Projects, Vendors
from app.schemas.project import Project, ProjectCreate, ProjectSummary, ProjectUpdate
from app.schemas.vendor import Vendor, VendorCreate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, projects: Projects) -> Project:
    """Create a project. Criteria are materialized (auto criteria added) and weights normalized."""
    return projects.create(data)


@router.get("", response_model=list[ProjectSummary])
def list_projects(projects: Projects) -> list[ProjectSummary]:
    return projects.list()


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: int, projects: Projects) -> Project:
    return projects.get(project_id)


@router.put("/{project_id}", response_model=Project)
def update_project(project_id: int, data: ProjectUpdate, projects: Projects) -> Project:
    """Replace a project. Criteria may be sent back exactly as returned by GET (including auto ones)."""
    return projects.update(project_id, data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, projects: Projects) -> Response:
    projects.delete(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/vendors", response_model=Vendor, status_code=status.HTTP_201_CREATED)
def create_vendor(project_id: int, data: VendorCreate, vendors: Vendors) -> Vendor:
    return vendors.create(project_id, data)


@router.get("/{project_id}/vendors", response_model=list[Vendor])
def list_vendors(project_id: int, vendors: Vendors) -> list[Vendor]:
    return vendors.list(project_id)

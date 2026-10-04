from fastapi import APIRouter, Response, status

from app.api.deps import Vendors
from app.schemas.vendor import Vendor, VendorCreate

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.get("/{vendor_id}", response_model=Vendor)
def get_vendor(vendor_id: int, vendors: Vendors) -> Vendor:
    return vendors.get(vendor_id)


@router.put("/{vendor_id}", response_model=Vendor)
def update_vendor(vendor_id: int, data: VendorCreate, vendors: Vendors) -> Vendor:
    return vendors.update(vendor_id, data)


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(vendor_id: int, vendors: Vendors) -> Response:
    vendors.delete(vendor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

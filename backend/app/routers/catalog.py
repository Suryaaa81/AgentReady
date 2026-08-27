from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.merchant import Merchant
from app.schemas.catalog import CatalogImportResult, ProductResponse
from app.security import get_current_merchant
from app.services import catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/products", response_model=list[ProductResponse])
def get_all_products(
    current: Merchant = Depends(get_current_merchant), db: Session = Depends(get_db)
):
    return catalog.get_products(db, current.id)


@router.post("/import", response_model=CatalogImportResult)
async def import_catalog(
    file: UploadFile = File(...),
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    if file.content_type not in ("text/csv", "application/vnd.ms-excel"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    if file.size and file.size > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 2MB limit")

    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 CSV")

    return catalog.import_catalog_csv(db, current.id, csv_text)


@router.get("/search", response_model=list[ProductResponse])
def search_products(
    query: str,
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    return catalog.search_products_query(db, current.id, query)

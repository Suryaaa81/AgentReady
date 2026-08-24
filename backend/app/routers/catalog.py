from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.catalog import ProductResponse, CatalogImportResult
from app.services import catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/products", response_model=list[ProductResponse])
def get_all_products(merchant_id: str, db: Session = Depends(get_db)):
    return catalog.get_products(db, merchant_id)


@router.post("/import", response_model=CatalogImportResult)
async def import_catalog(merchant_id: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 CSV")
    
    return catalog.import_catalog_csv(db, merchant_id, csv_text)


@router.get("/search", response_model=list[ProductResponse])
def search_products(merchant_id: str, query: str, db: Session = Depends(get_db)):
    return catalog.search_products_query(db, merchant_id, query)

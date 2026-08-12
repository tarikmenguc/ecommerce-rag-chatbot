"""Excel/CSV Import Router — Upload, preview, and template endpoints."""
from __future__ import annotations

import io
import logging
import uuid
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ShopifyJob, ShopifyJobStatus

log = logging.getLogger("app.excel_import")
router = APIRouter(prefix="/import", tags=["import"])

# Required columns in the uploaded file
REQUIRED_COLUMNS = {"title", "price"}

# All recognized columns (others are silently ignored)
KNOWN_COLUMNS = {
    "title", "price", "category", "vendor", "sku", "barcode",
    "description", "image_url", "tags", "variant_option", "stock_quantity",
}


def _read_file(file: UploadFile) -> pd.DataFrame:
    """Read an uploaded file into a pandas DataFrame."""
    filename = (file.filename or "").lower()
    contents = file.file.read()

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(contents), engine="openpyxl")
    elif filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents))
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload .xlsx or .csv"
        )

    # Normalize column names: lowercase + strip whitespace
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _validate(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Validate rows and return a list of error dicts."""
    errors: List[Dict[str, Any]] = []

    # Check required columns exist
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        errors.append({
            "row": 0,
            "field": ", ".join(missing_cols),
            "message": f"Missing required column(s): {', '.join(missing_cols)}"
        })
        return errors  # Can't proceed without required columns

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # +2 because Excel rows are 1-indexed and row 1 is header

        # Title check
        title = row.get("title")
        if pd.isna(title) or str(title).strip() == "":
            errors.append({"row": row_num, "field": "title", "message": "Title is empty"})

        # Price check
        price = row.get("price")
        if pd.isna(price):
            errors.append({"row": row_num, "field": "price", "message": "Price is empty"})
        else:
            try:
                p = float(str(price).replace(",", ".").replace("$", "").replace("₺", "").strip())
                if p < 0:
                    errors.append({"row": row_num, "field": "price", "message": "Price cannot be negative"})
            except (ValueError, TypeError):
                errors.append({"row": row_num, "field": "price", "message": f"Invalid price value: {price}"})

        # Image URL sanity check (optional but warn)
        img = row.get("image_url")
        if not pd.isna(img) and str(img).strip() and not str(img).strip().startswith("http"):
            errors.append({"row": row_num, "field": "image_url", "message": f"image_url should start with http(s): {img}"})

    return errors


def _clean_price(val: Any) -> str:
    """Normalize a price value to a clean decimal string."""
    if pd.isna(val):
        return "0.00"
    s = str(val).replace(",", ".").replace("$", "").replace("₺", "").replace(" ", "")
    try:
        return f"{float(s):.2f}"
    except (ValueError, TypeError):
        return "0.00"


@router.post("/preview")
async def preview_file(file: UploadFile = File(...)):
    """Parse uploaded file and return a preview (first 10 rows) + validation results."""
    df = _read_file(file)

    if df.empty:
        raise HTTPException(status_code=400, detail="File is empty.")

    errors = _validate(df)

    # Build preview rows (first 10)
    preview_rows = []
    for idx, row in df.head(10).iterrows():
        preview_rows.append({
            "row_number": int(idx) + 2,
            "title": str(row.get("title", "")) if not pd.isna(row.get("title")) else "",
            "price": str(row.get("price", "")) if not pd.isna(row.get("price")) else "",
            "image_url": str(row.get("image_url", "")) if not pd.isna(row.get("image_url")) else "",
            "vendor": str(row.get("vendor", "")) if not pd.isna(row.get("vendor")) else "",
            "category": str(row.get("category", "")) if not pd.isna(row.get("category")) else "",
            "has_image": bool(not pd.isna(row.get("image_url")) and str(row.get("image_url", "")).strip().startswith("http")),
        })

    # Detected columns
    detected = [c for c in df.columns if c in KNOWN_COLUMNS]
    unknown = [c for c in df.columns if c not in KNOWN_COLUMNS]

    return {
        "total_rows": len(df),
        "detected_columns": detected,
        "unknown_columns": unknown,
        "preview": preview_rows,
        "errors": errors,
        "valid_count": len(df) - len([e for e in errors if e["row"] > 0]),
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload Excel/CSV, validate, and create ShopifyJob entries for each valid row."""
    df = _read_file(file)

    if df.empty:
        raise HTTPException(status_code=400, detail="File is empty.")

    errors = _validate(df)

    # Block upload if there are critical errors (missing columns)
    col_errors = [e for e in errors if e["row"] == 0]
    if col_errors:
        raise HTTPException(status_code=422, detail={
            "message": "Missing required columns",
            "errors": col_errors
        })

    # Row-level errors — skip those rows but import the rest
    error_rows = {e["row"] for e in errors if e["row"] > 0}

    batch_id = str(uuid.uuid4())
    jobs_created = 0
    skipped = 0

    for idx, row in df.iterrows():
        row_num = int(idx) + 2
        if row_num in error_rows:
            skipped += 1
            continue

        # Clean and extract values
        title = str(row.get("title", "")).strip()
        price = _clean_price(row.get("price"))
        description = str(row.get("description", "")) if not pd.isna(row.get("description")) else ""
        image_url = str(row.get("image_url", "")) if not pd.isna(row.get("image_url")) else ""
        vendor = str(row.get("vendor", "")) if not pd.isna(row.get("vendor")) else ""
        category = str(row.get("category", "")) if not pd.isna(row.get("category")) else ""
        sku_val = str(row.get("sku", "")) if not pd.isna(row.get("sku")) else ""
        barcode_val = str(row.get("barcode", "")) if not pd.isna(row.get("barcode")) else ""
        tags_val = str(row.get("tags", "")) if not pd.isna(row.get("tags")) else ""
        variant = str(row.get("variant_option", "")) if not pd.isna(row.get("variant_option")) else ""

        stock_qty = None
        if "stock_quantity" in df.columns and not pd.isna(row.get("stock_quantity")):
            try:
                stock_qty = int(float(row["stock_quantity"]))
            except (ValueError, TypeError):
                stock_qty = None

        job = ShopifyJob(
            batch_id=batch_id,
            shopify_product_id="",  # Will be set after Shopify POST
            barcode=barcode_val,
            original_title=title,
            original_description=description,
            image_url=image_url,
            status=ShopifyJobStatus.PENDING,
            # --- New Excel fields ---
            is_new_product=True,
            price=price,
            vendor=vendor,
            product_type=category,
            tags=tags_val,
            sku=sku_val,
            variant_option=variant,
            stock_quantity=stock_qty,
            source="excel",
        )
        session.add(job)
        jobs_created += 1

    await session.commit()

    log.info(f"Excel import: {jobs_created} jobs created, {skipped} skipped, batch={batch_id}")

    return {
        "status": "success",
        "batch_id": batch_id,
        "jobs_created": jobs_created,
        "skipped": skipped,
        "errors": [e for e in errors if e["row"] > 0],
    }


@router.get("/template")
async def download_template():
    """Generate and return a sample Excel template file."""
    df = pd.DataFrame({
        "title": ["Example Product Name", "Another Product"],
        "price": [29.99, 49.50],
        "category": ["Electronics", "Clothing"],
        "vendor": ["BrandName", "AnotherBrand"],
        "sku": ["SKU-001", "SKU-002"],
        "barcode": ["1234567890123", "9876543210987"],
        "description": ["Waterproof, lightweight, durable", "Cotton, breathable, soft"],
        "image_url": ["https://example.com/product1.jpg", "https://example.com/product2.jpg"],
        "tags": ["electronics, gadget", "clothing, summer"],
        "variant_option": ["", "Red, L"],
        "stock_quantity": [100, 50],
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Products")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=shopify_import_template.xlsx"}
    )

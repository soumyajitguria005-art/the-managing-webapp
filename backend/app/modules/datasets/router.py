from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.datasets.importer import (
    DatasetActivationService, SourceImportService, ValidationErrorDetail
)
from app.modules.datasets.models import DatasetVersion
from app.modules.datasets.schemas import (
    DatasetActivationRequest, DatasetActivationResponse,
    DatasetVersionResponse, ImportJobResponse, ValidationResultResponse
)
from app.modules.integration.models import ImportJob

router = APIRouter(prefix="/datasets", tags=["datasets"])

@router.post("/validate", response_model=ValidationResultResponse)
async def validate_dataset_source(
    request: Request,
    file: Optional[UploadFile] = File(None)
):
    """Validate canonical dataset payload without importing into database."""
    if file:
        raw_bytes = await file.read()
    else:
        raw_bytes = await request.body()

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No JSON content or file provided for validation"
        )

    try:
        ds, raw_dict, sha256 = SourceImportService.validate_source(raw_bytes)
        return ValidationResultResponse(
            is_valid=True,
            source_sha256=sha256,
            dataset_id=ds.dataset_id,
            institute=ds.institute,
            errors=[],
            summary_counts={
                "rooms": len(ds.rooms),
                "faculty": len(ds.faculty),
                "student_groups": len(ds.student_groups),
                "courses": len(ds.courses),
                "sessions": len(ds.sessions),
                "booking_requests": len(ds.booking_requests),
                "cancellations": len(ds.cancellations),
                "exams": len(ds.exams),
            }
        )
    except ValidationErrorDetail as e:
        sha256 = SourceImportService.calculate_sha256(raw_bytes)
        return ValidationResultResponse(
            is_valid=False,
            source_sha256=sha256,
            errors=e.errors,
            summary_counts={}
        )

@router.post("/import", response_model=ImportJobResponse, status_code=status.HTTP_201_CREATED)
async def import_dataset(
    request: Request,
    file: Optional[UploadFile] = File(None),
    allow_duplicate: bool = False,
    db: Session = Depends(get_db)
):
    """Transactionally import a validated canonical dataset into PostgreSQL."""
    filename = "cit_public.json"
    if file:
        raw_bytes = await file.read()
        filename = file.filename or filename
    else:
        raw_bytes = await request.body()

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No JSON content or file provided for import"
        )

    try:
        job, dsv, report = SourceImportService.import_source(
            db=db,
            raw_bytes=raw_bytes,
            original_filename=filename,
            allow_duplicate=allow_duplicate
        )
        return ImportJobResponse(
            id=job.id,
            dataset_version_id=dsv.id,
            status=job.status,
            report_json=report,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at
        )
    except ValidationErrorDetail as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": e.message, "errors": e.errors}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=ImportJobResponse)
def get_import_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve import job status and full execution report."""
    job = db.execute(select(ImportJob).where(ImportJob.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import job {job_id} not found")
    return ImportJobResponse(
        id=job.id,
        dataset_version_id=job.dataset_version_id,
        status=job.status,
        report_json=job.report_json,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at
    )

@router.get("/{dataset_version_id}/reconciliation")
def get_reconciliation_report(dataset_version_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve complete post-import entity-level and relationship reconciliation report."""
    dsv = db.execute(select(DatasetVersion).where(DatasetVersion.id == dataset_version_id)).scalar_one_or_none()
    if not dsv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset version {dataset_version_id} not found")
    return SourceImportService.build_reconciliation_report(db, dataset_version_id)

@router.post("/{dataset_version_id}/activate", response_model=DatasetActivationResponse)
def activate_dataset_version(
    dataset_version_id: uuid.UUID,
    payload: DatasetActivationRequest = DatasetActivationRequest(),
    db: Session = Depends(get_db)
):
    """Explicitly activate a validated dataset version with atomic deactivation of previous version."""
    try:
        activation = DatasetActivationService.activate_dataset(
            db=db,
            dataset_version_id=dataset_version_id,
            reason=payload.reason
        )
        return DatasetActivationResponse(
            id=activation.id,
            institute_id=activation.institute_id,
            dataset_version_id=activation.dataset_version_id,
            activated_at=activation.activated_at,
            reason=activation.reason,
            status="ACTIVE"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("", response_model=List[DatasetVersionResponse])
def list_dataset_versions(db: Session = Depends(get_db)):
    """List all dataset versions in the system with their status and activation state."""
    versions = db.execute(
        select(DatasetVersion).order_by(DatasetVersion.version_number.desc())
    ).scalars().all()
    return [
        DatasetVersionResponse(
            id=v.id,
            institute_id=v.institute_id,
            external_dataset_id=v.external_dataset_id,
            version_number=v.version_number,
            source_sha256=v.source_sha256,
            status=v.status,
            imported_at=v.imported_at,
            activated_at=v.activated_at
        )
        for v in versions
    ]

@router.get("/active", response_model=Optional[DatasetVersionResponse])
def get_active_dataset(db: Session = Depends(get_db)):
    """Retrieve the currently active dataset version."""
    active_dsv = DatasetActivationService.get_active_dataset(db)
    if not active_dsv:
        return None
    return DatasetVersionResponse(
        id=active_dsv.id,
        institute_id=active_dsv.institute_id,
        external_dataset_id=active_dsv.external_dataset_id,
        version_number=active_dsv.version_number,
        source_sha256=active_dsv.source_sha256,
        status=active_dsv.status,
        imported_at=active_dsv.imported_at,
        activated_at=active_dsv.activated_at
    )

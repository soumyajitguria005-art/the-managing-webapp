from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ValidationIssue(BaseModel):
    loc: List[Any]
    path: str
    msg: str
    type: str

class ValidationResultResponse(BaseModel):
    is_valid: bool
    source_sha256: str
    dataset_id: Optional[str] = None
    institute: Optional[str] = None
    errors: List[ValidationIssue] = Field(default_factory=list)
    summary_counts: Dict[str, int] = Field(default_factory=dict)

class ImportJobResponse(BaseModel):
    id: uuid.UUID
    dataset_version_id: Optional[uuid.UUID] = None
    status: str
    report_json: Dict[str, Any]
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

class DatasetVersionResponse(BaseModel):
    id: uuid.UUID
    institute_id: uuid.UUID
    external_dataset_id: str
    version_number: int
    source_sha256: str
    status: str
    imported_at: datetime
    activated_at: Optional[datetime] = None

class DatasetActivationRequest(BaseModel):
    reason: Optional[str] = "Manual activation by administrator"

class DatasetActivationResponse(BaseModel):
    id: uuid.UUID
    institute_id: uuid.UUID
    dataset_version_id: uuid.UUID
    activated_at: datetime
    reason: Optional[str] = None
    status: str = "ACTIVE"

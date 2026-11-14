from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Response, UploadFile

from app.api.deps import get_current_user, get_document_processor, get_document_service
from app.api.schemas.document import DocumentRead
from app.core.security import CurrentUser
from app.core.types import DocumentScope
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("", status_code=202, response_model=DocumentRead)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    scope: DocumentScope = Form(...),
    user: CurrentUser = Depends(get_current_user),
    documents: DocumentService = Depends(get_document_service),
    process: Callable[[int], None] = Depends(get_document_processor),
) -> DocumentRead:
    # Read one byte past the limit so oversized files are rejected without loading them whole.
    data = file.file.read(documents.max_upload_bytes + 1)
    document = documents.upload(
        user, scope, file.filename or "", file.content_type or "application/octet-stream", data
    )
    background_tasks.add_task(process, document.id)
    return DocumentRead.model_validate(document)


@router.get("", response_model=list[DocumentRead])
def list_documents(
    scope: DocumentScope = Query(...),
    user: CurrentUser = Depends(get_current_user),
    documents: DocumentService = Depends(get_document_service),
) -> list[DocumentRead]:
    return [DocumentRead.model_validate(d) for d in documents.list_documents(user, scope)]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    user: CurrentUser = Depends(get_current_user),
    documents: DocumentService = Depends(get_document_service),
) -> DocumentRead:
    return DocumentRead.model_validate(documents.get_document(user, document_id))


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    user: CurrentUser = Depends(get_current_user),
    documents: DocumentService = Depends(get_document_service),
) -> Response:
    documents.delete_document(user, document_id)
    return Response(status_code=204)

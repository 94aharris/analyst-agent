from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .server import MyChatKitServer
from .datastore import RawAttachmentStore, SqliteStore
from chatkit.server import StreamingResult
from chatkit.types import AttachmentCreateParams


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI()

# Add CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

datastore = SqliteStore()
attachment_store = RawAttachmentStore(metadata_store=datastore)

server = MyChatKitServer(datastore, attachment_store)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root_page() -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Chat interface not found")
    return FileResponse(index_file)


@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    result = await server.process(await request.body(), {})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    else:
        return Response(content=result.json, media_type="application/json")


@app.post("/attachments/upload")
async def upload_attachment(request: Request):
    """Upload an attachment and return its metadata."""
    # Parse the multipart form data
    form = await request.form()

    # Get the uploaded file
    uploaded_file = form.get("file")
    if not uploaded_file:
        raise HTTPException(status_code=422, detail="No file provided")

    # Get file metadata
    attachment_name = uploaded_file.filename or "unnamed"
    attachment_mime_type = uploaded_file.content_type or "application/octet-stream"

    # Read file bytes
    file_bytes = await uploaded_file.read()

    # Create attachment using the store
    attachment_params = AttachmentCreateParams(
        name=attachment_name,
        size=len(file_bytes),
        mime_type=attachment_mime_type,
    )

    # Context dict with file bytes for the attachment store
    context = {"file_bytes": file_bytes}

    attachment = await attachment_store.create_attachment(attachment_params, context)

    # Return the attachment as JSON
    return JSONResponse(content=attachment.model_dump(mode="json"))


@app.get("/attachments/{attachment_id}/{filename}")
async def get_attachment(attachment_id: str, filename: str):
    """Serve uploaded attachment files."""
    attachment_path = Path("data/attachments") / attachment_id / filename

    if not attachment_path.exists():
        raise HTTPException(status_code=404, detail="Attachment not found")

    return FileResponse(attachment_path)

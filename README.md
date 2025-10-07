# Analyst Agent

> **⚠️ Proof of concept:** This repository is for experimentation only. It is not hardened for production, assumes a single trusted user, and is vulnerable to prompt-injection and other security issues.

A full-stack ChatKit experiment that lets you chat with Claude via a FastAPI backend, stream responses live, and upload attachments that are added to the model context.

## Highlights

- **Realtime chat** powered by OpenAI ChatKit + a custom `ChatKitServer` implementation.
- **Attachment uploads** stored on disk (`data/attachments/…`) with metadata persisted to SQLite and surfaced to Claude.
- **Choose your UI**: a production-ready React/Vite client (`frontend/`) and a lightweight static demo under `/static`.
- **Claude CLI integration**: the backend shells out to the `claude` command and injects attachment info through both the prompt and `CHATKIT_ATTACHMENTS` env payloads.

## Architecture

### Backend (`src/`)

- FastAPI application (`src/main.py`) exposes:
  - `POST /chatkit` — ChatKit ingress (streams SSE or JSON)
  - `POST /attachments/upload` — direct upload endpoint used by the React composer
  - `GET /attachments/{attachment_id}/{filename}` — serves stored files and previews
- `MyChatKitServer` (`src/server.py`)
  - Streams Claude CLI output back to ChatKit
  - Tracks conversation sessions per thread
  - Extracts attachment paths + previews and appends them to the prompt
  - Passes attachment metadata to the CLI via the `CHATKIT_ATTACHMENTS` environment variable
- Persistence layer (`src/datastore/`)
  - `SqliteStore` handles threads, items, and attachment metadata (JSON blobs inside `chatkit.sqlite`)
  - `RawAttachmentStore` saves attachment bytes to disk and proxies metadata calls to `SqliteStore`

### Frontend (`frontend/`)

- React + Vite application that embeds `<ChatKit/>`
- Custom fetch wrapper keeps JSON headers for chat but defers to browser-controlled multipart headers for uploads
- Proxy in `vite.config.js` forwards API traffic to the FastAPI server during development

### Static Demo (`static/`)

- Minimal HTML + JS sample that mounts `<openai-chatkit>` directly
- Served at `http://localhost:8000/` when the FastAPI app is running
- Useful for manual smoke tests; still missing full feature parity with the React client

## Prerequisites

- Python 3.13+
- Node.js 18+
- npm (or pnpm/yarn if you prefer)
- [Claude CLI](https://www.anthropic.com/product/claude) installed and authenticated — the backend executes the `claude` binary on the host machine
- Optional but recommended: [uv](https://github.com/astral-sh/uv) for Python dependency management (a `uv.lock` file lives in the repo)

## Getting Started

### 1. Backend (FastAPI + ChatKit)

```bash
# Install dependencies (pick one)
uv sync                 # if you use uv
# OR
pip install -e .        # standard pip install with pyproject

# Run the API server
uvicorn src.main:app --reload --host localhost --port 8000
```

The backend listens on `http://localhost:8000` and serves both the ChatKit endpoint and the static demo.

> **Tip:** The first chat request will download ChatKit models/files; keep the server logs open to inspect upload IDs and attachment processing.

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install          # once
npm run dev
```

Open `http://localhost:5173` and start chatting. The dev server proxies `/chatkit` and `/attachments` to the backend automatically.

### 3. Optional: Static Demo

With only the FastAPI server running, navigate to `http://localhost:8000/` to use the raw `<openai-chatkit>` element.

## Attachment Workflow

1. The React composer (or any client pointing to `/attachments/upload`) sends `multipart/form-data` with a `file` field.
2. `RawAttachmentStore` saves the file under `data/attachments/<attachment_id>/` and records metadata (including the physical filename) in `metadata.json`.
3. Metadata is persisted to SQLite via `SqliteStore.save_attachment`, making future lookups consistent across restarts.
4. When the next chat message arrives, `MyChatKitServer.respond`:
   - Resolves each attachment’s local path
   - Adds a formatted attachment summary + optional text preview to the prompt sent to Claude
   - Exports `CHATKIT_ATTACHMENTS=[{"id":…, "path":…, …}]` for the Claude CLI so custom tooling can read bytes directly if desired
5. The assistant’s streamed response flows back to ChatKit and the UI.

### Storage Layout

```
data/
  attachments/
    att_xxx/
      metadata.json      # id, name, mime_type, stored_name, size, created_at
      <stored_name>      # actual bytes written by the upload handler
chatkit.sqlite           # threads, items, and attachment metadata JSON blobs
```

Old attachments can be reclaimed by deleting the directory and calling `DELETE /attachments/<id>` (not yet exposed; coming soon).

## Project Structure

```
.
├── frontend/                # React + Vite client
│   ├── src/App.jsx          # ChatKit integration
│   └── vite.config.js       # Proxy configuration
├── src/
│   ├── main.py              # FastAPI wiring + endpoints
│   ├── server.py            # MyChatKitServer (Claude streaming + attachments)
│   └── datastore/
│       ├── sqlite_store.py  # SQLite persistence for threads/items/attachments
│       └── attachment_store.py  # Raw filesystem store with metadata hooks
├── static/                  # Vanilla JS demo assets
├── chatkit.sqlite           # Created at runtime
├── data/attachments/        # Attachment payloads (runtime)
├── pyproject.toml           # Backend dependencies
└── README.md
```

## Current Status & Roadmap

- ✅ ChatKit backend + attachment persistence
- ✅ React client with working uploads
- ⚠️ Static demo still lacks attachment handling; main chat container renders but needs polish
- ⏭ Planned: admin endpoint to purge attachments, richer attachment previews, optional S3 backend

## Troubleshooting

- **422 on upload** – ensure the frontend keeps the request `Content-Type` unset for `FormData` (already handled in `frontend/src/App.jsx`).
- **Claude command not found** – install the `claude` CLI and make sure it’s on your `PATH` before starting the server.
- **Old attachments missing** – check `data/attachments/<id>/metadata.json` to confirm the stored filename, then verify filesystem permissions.

Need a hand? Open an issue or reach out in the repo discussions.

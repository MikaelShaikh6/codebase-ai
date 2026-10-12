# Codebase AI

Codebase AI is a full-stack codebase knowledge assistant. Upload a ZIP archive
of a software project, index its source code, and ask questions that are
answered with retrieved code context and source citations.

This is a portfolio/demo project designed to demonstrate retrieval-augmented
generation (RAG), secure ingestion, vector search, background processing, and
full-stack integration.

## What it does

1. A user creates an account or signs in.
2. The user uploads a ZIP archive.
3. The backend validates the archive and protects against path traversal.
4. Python source files are parsed into semantic AST-based chunks.
5. Chunks are embedded with FastEmbed.
6. Embeddings and source metadata are indexed in Qdrant.
7. A user question is embedded and searched within the selected project.
8. Retrieved source context is sent to a configured language model.
9. The answer is returned with citations containing file paths and line ranges.

## Architecture

```text
Next.js frontend
        |
        | REST + bearer token
        v
FastAPI backend
        |
        +--> SQLite or PostgreSQL project metadata
        +--> Local files or S3-compatible object storage
        +--> FastEmbed local embeddings
        +--> Qdrant vector search
        +--> Ollama or OpenAI-compatible generation
```

### Request and indexing flow

```text
ZIP upload
    |
    v
Validation and safe extraction
    |
    v
Python AST chunking
    |
    v
FastEmbed vectors
    |
    v
Qdrant project-scoped indexing
    |
    v
Question embedding and retrieval
    |
    v
Grounded answer generation
    |
    v
Answer with source citations
```

## Technology

### Frontend

- Next.js
- React
- TypeScript
- Responsive project workspace and chat UI

### Backend

- FastAPI
- SQLModel
- SQLite for local development
- PostgreSQL-compatible database configuration
- JWT bearer authentication
- PBKDF2 password hashing
- In-memory request rate limiting

### AI and search

- FastEmbed for local embedding generation
- Qdrant for vector indexing and similarity search
- Ollama for local model inference
- Generic OpenAI-compatible provider support for hosted inference

### Operations

- Docker and Docker Compose
- GitHub Actions CI
- Render Blueprint
- S3-compatible storage support, including Cloudflare R2
- End-to-end backend tests

## Repository structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/             # REST endpoints
│   │   ├── core/            # Database, auth, and rate limiting
│   │   ├── generation/      # Ollama and OpenAI-compatible providers
│   │   ├── ingestion/       # ZIP validation, extraction, and chunking
│   │   ├── models/          # SQLModel database models
│   │   ├── retrieval/       # Project-scoped vector retrieval
│   │   └── services/        # Embeddings, Qdrant, storage, and workers
│   └── tests/               # Backend unit, integration, and E2E tests
├── frontend/
│   └── app/                 # Next.js workspace and chat interface
├── .github/workflows/       # GitHub Actions CI
├── docker-compose.yml       # Local frontend/backend/Qdrant stack
├── render.yaml              # Cloud deployment blueprint
├── DEPLOYMENT.md            # Optional cloud deployment instructions
└── .env.example             # Configuration template
```

## Quick start with Docker

### Prerequisites

Install:

- Docker Engine or Docker Desktop
- Docker Compose
- Ollama, if using the default local model provider

For local model inference, install the configured model:

```bash
ollama pull qwen3:4b
```

On Linux, Ollama may need to listen beyond loopback so the backend container
can reach it:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

### Configure the environment

From the repository root:

```bash
cp .env.example .env
```

The `.env` file is ignored by Git. Never commit API keys, database passwords,
or storage credentials.

The default local configuration uses:

```env
AUTH_REQUIRED=false
STORAGE_BACKEND=local
LLM_PROVIDER=ollama
QDRANT_URL=http://qdrant:6333
```

If `host.docker.internal` is not reachable from your Docker environment,
override `OLLAMA_URL` in `.env` with the host address that your backend
container can reach.

### Start the application

```bash
docker compose up --build
```

Open the frontend at:

```text
http://localhost:3000
```

The other local services are:

```text
FastAPI: http://localhost:8000
Qdrant:  http://localhost:6333
Health:  http://localhost:8000/health
```

Stop the stack with:

```bash
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to delete
the local database, uploaded project data, and Qdrant index volumes.

## Local development without Docker

### Backend

Create or activate a Python 3.12 environment, then install dependencies:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### Frontend

In a second terminal:

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open `http://localhost:3000`.

## Configuration

Copy [.env.example](./.env.example) to `.env` and change only the values
needed for your environment.

| Variable | Purpose | Local default |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Browser-visible backend URL | `http://localhost:8000` |
| `FRONTEND_ORIGINS` | Allowed CORS origins | Local frontend URLs |
| `AUTH_REQUIRED` | Require bearer authentication | `false` |
| `JWT_SECRET` | Secret used to sign access tokens | Development placeholder |
| `DATABASE_URL` | SQLModel database connection | Local SQLite |
| `QDRANT_URL` | Qdrant HTTP endpoint | `http://qdrant:6333` |
| `QDRANT_COLLECTION` | Qdrant collection name | `codebase_chunks` |
| `STORAGE_BACKEND` | `local` or `s3` archive storage | `local` |
| `RUN_PROJECT_WORKER` | Enable persisted background worker | `false` outside Compose |
| `LLM_PROVIDER` | `ollama` or `openai_compatible` | `ollama` |
| `OLLAMA_URL` | Local Ollama endpoint | Host-dependent |
| `OLLAMA_MODEL` | Local Ollama model | `qwen3:4b` |
| `OPENAI_BASE_URL` | OpenAI-compatible API base URL | OpenAI default |
| `OPENAI_API_KEY` | Hosted model API key | Empty |
| `OPENAI_MODEL` | Hosted model name | `gpt-4o-mini` |
| `EMBEDDING_MODEL` | FastEmbed model name | `BAAI/bge-small-en-v1.5` |

For S3-compatible storage, also configure:

```env
S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_BUCKET=
S3_REGION=auto
```

## Authentication

The backend provides:

```text
POST /auth/register
POST /auth/login
```

Passwords are hashed with PBKDF2 and are never stored as plaintext.

When authentication is enabled, project routes require a bearer token:

```text
Authorization: Bearer <access-token>
```

Projects are ownership-scoped, so users can only list, process, inspect, and
chat with their own projects.

For a public deployment, set a strong random `JWT_SECRET` and:

```env
AUTH_REQUIRED=true
```

## API overview

```text
GET  /health

POST /auth/register
POST /auth/login

GET  /projects
POST /projects/upload
GET  /projects/{project_id}
GET  /projects/{project_id}/status
POST /projects/{project_id}/chat
```

Example health check:

```bash
curl http://localhost:8000/health
```

Example login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your-password"}'
```

## Testing and CI

Run the backend tests:

```bash
cd backend
.venv/bin/python -m pytest -q
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

GitHub Actions runs the same backend and frontend checks on pushes and pull
requests. The suite includes ingestion, chunking, embeddings, Qdrant,
retrieval, generation, authentication, rate limiting, storage, API routes,
background processing, and end-to-end coverage.

## Security and limits

The application includes:

- ZIP path traversal protection.
- Upload and extracted-content size limits.
- Ignored dependency and generated directories.
- Project-scoped Qdrant filters.
- Trusted application-generated citations.
- Password hashing.
- Signed expiring access tokens.
- Per-client limits for login, registration, uploads, and chat.
- Environment-based secret configuration.

Current request limits are:

```text
Registration: 5 per hour
Login:        10 per 15 minutes
Uploads:      5 per hour
Chat:         20 per hour
```

Rate-limit counters are in memory. A multi-instance deployment should use a
shared Redis-backed limiter.

## Deployment status

This project is designed to run locally and is cloud-ready, but it does not
need to be deployed to be evaluated as a portfolio project. The repository
contains:

- [DEPLOYMENT.md](./DEPLOYMENT.md) for optional cloud setup.
- [render.yaml](./render.yaml) for a Render Blueprint.
- Managed PostgreSQL configuration.
- S3-compatible storage configuration.
- Hosted OpenAI-compatible inference support.

The optional cloud architecture uses managed PostgreSQL, object storage,
Qdrant, and hosted model inference. Free-tier limits, sleep behavior, quotas,
and billing policies vary by provider, so verify current terms before
deploying.

## Known limitations

- Only Python source files are currently chunked semantically.
- Classes are initially kept as intact chunks; nested methods are not emitted
  separately.
- Local FastAPI background execution is process-local; the persisted worker is
  intended for the current single-instance demo.
- In-memory rate limiting is not shared between multiple backend instances.
- The frontend does not yet have an automated browser test suite.
- The current chat endpoint waits for the model response instead of streaming
  tokens.
- SQLite and local storage are intended for development; managed PostgreSQL
  and S3-compatible storage are intended for cloud use.

## Interview talking points

This project demonstrates:

- Why semantic chunking is preferable to arbitrary character splitting for
  source code.
- Why indexing and querying must use the same embedding space.
- How project IDs prevent cross-project retrieval.
- Why citations should come from trusted retrieved metadata rather than model
  generated file paths.
- Why a request-scoped background task is not sufficient for durable jobs.
- Why local files and SQLite need managed replacements for horizontal scaling.
- Why authentication, ownership checks, rate limits, and upload validation
  are necessary before public access.


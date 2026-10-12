# Codebase AI frontend

The Next.js frontend talks to the FastAPI backend at `http://localhost:8000`
by default. Set `NEXT_PUBLIC_API_URL` when the backend is hosted elsewhere.

## Getting Started

Install dependencies and start the frontend:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

In a second terminal, start the backend from the repository root:

```bash
cd backend
../backend/.venv/bin/uvicorn app.main:app --reload --port 8000
```

The upload form sends ZIP archives to `POST /projects/upload` and checks
`GET /health` to show the backend connection status. The backend accepts the
frontend origins in `FRONTEND_ORIGINS` as a comma-separated list.

For example:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Docker Compose

From the repository root, start the frontend, backend, and Qdrant:

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The API is available at
[http://localhost:8000](http://localhost:8000), and Qdrant is available at
[http://localhost:6333](http://localhost:6333).

Compose persists SQLite, uploaded project files, and Qdrant data in named
volumes. Ollama is expected to run on the host by default; set
`OLLAMA_URL` appropriately if it runs elsewhere.

For a cloud deployment, see the repository-level
[DEPLOYMENT.md](../DEPLOYMENT.md).

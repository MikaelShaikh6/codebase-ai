# Cloud deployment

The repository includes a [Render Blueprint](./render.yaml) for deploying the
frontend and backend as Docker web services. Qdrant and Ollama remain external
dependencies because they need persistent storage and model-serving
resources that should not be tied to a web-service container.

## Prerequisites

Create:

1. A Qdrant Cloud cluster and API key.
2. An Ollama-compatible HTTPS endpoint with the `qwen3:4b` model available.
3. A Render account connected to this repository.

The Ollama URL must be reachable from Render. `localhost` and
`host.docker.internal` only work for local development and must not be used for
the deployed backend.

For local Docker Compose development, Ollama runs on the host while the
backend runs in a container. Compose reads `OLLAMA_URL` from the repository's
`.env` file and uses `http://host.docker.internal:11434` only as its fallback.
Create the local environment file before starting Compose:

```bash
cp .env.example .env
```

If your Docker host requires a specific reachable address, edit `.env`:

```text
OLLAMA_URL=http://your-host-address:11434
```

The `.env` file is ignored by Git and must not be committed. On Linux,
configure Ollama to listen beyond loopback before starting Compose:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Then confirm the model is installed:

```bash
ollama pull qwen3:4b
curl http://localhost:11434/api/tags
```

If Ollama is already managed as a system service, set its service
environment to `OLLAMA_HOST=0.0.0.0:11434`, restart the service, and keep the
local firewall restricted to trusted networks.

## Deploy with Render

1. In Render, choose **New → Blueprint** and select this repository.
2. Render reads [render.yaml](./render.yaml) and creates the backend and
   frontend services.
3. Enter the secret values when Render prompts for them:
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
   - `OLLAMA_URL`
4. Wait for the backend health check at `/health` and the frontend deployment
   to become live.
5. Open the frontend service URL and upload a small test project.
6. Confirm that the project reaches `ready`, then send a chat question.

The blueprint connects the services using Render's generated
`RENDER_EXTERNAL_URL` values. `NEXT_PUBLIC_API_URL` is a frontend build-time
value, while `FRONTEND_ORIGINS` is a backend CORS value.

## Storage and operations

The backend uses SQLite and stores uploaded project files under `/app/data`.
The blueprint attaches a persistent Render disk so those files survive
deploys. Qdrant Cloud provides persistence for vectors.

This is a practical single-instance deployment for a portfolio project.
Before production scale, replace SQLite with managed PostgreSQL, move uploaded
archives to object storage, and replace in-process `BackgroundTasks` with a
durable worker queue. Those changes avoid data loss and make processing
resilient to restarts or multiple backend instances.

## Local alternative

For local development, continue using:

```bash
docker compose up --build
```

The Render blueprint is intentionally separate from
[docker-compose.yml](./docker-compose.yml), which is optimized for local
service names and local persistent volumes.

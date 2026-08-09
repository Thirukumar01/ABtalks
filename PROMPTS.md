# ABtalks – Autonomous AI Creator

An autonomous AI content creation platform.

## Features

- Autonomous AI agent
- Persona-based content generation
- News discovery
- Editorial decisions
- Automated publishing
- Scheduler
- Published posts feed
- Source tracking
- FastAPI backend

## Project Structure

- `backend/` – FastAPI backend
- `backend/app/` – application code
- `backend/data/` – local database/runtime data
- `backend/tests/` – tests

## Running the Backend

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

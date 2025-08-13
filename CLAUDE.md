# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a Course Materials RAG (Retrieval-Augmented Generation) system with the following key components:

- **FastAPI Backend** (`backend/app.py`): Serves both API endpoints and static frontend files
- **RAG System** (`backend/rag_system.py`): Main orchestrator that coordinates all components
- **Vector Store** (`backend/vector_store.py`): ChromaDB-based semantic search with dual collections:
  - `course_catalog`: Course metadata (titles, instructors, lessons)
  - `course_content`: Chunked course content for semantic search
- **Tool-Based AI Generation** (`backend/ai_generator.py`, `backend/search_tools.py`): Uses Anthropic Claude with function calling for course search and outline tools
- **Session Management** (`backend/session_manager.py`): Maintains conversation history per session
- **Document Processing** (`backend/document_processor.py`): Processes course documents into structured chunks

## Running the Application

### Quick Start
```bash
./run.sh
```

### Manual Start
```bash
cd backend && uv run uvicorn app:app --reload --port 8000
```

The application serves both the API and web interface at `http://localhost:8000`.

## Environment Configuration

Required environment variable in `.env`:
- `ANTHROPIC_API_KEY`: Your Anthropic API key for Claude

## Key Development Commands

- **Install dependencies**: `uv sync`
- **Run tests**: `npx playwright test`
- **Clear vector database**: Delete `backend/chroma_db/` directory

## Application Flow

1. On startup, the system loads documents from `docs/` folder into ChromaDB
2. User queries are processed by the RAG system using tool-based approach:
   - AI decides which tools to use (CourseSearchTool, CourseOutlineTool)
   - Tools perform semantic search against vector collections
   - AI generates responses based on retrieved context
3. Sessions maintain conversation history for context-aware responses

## Important Implementation Details

- The system uses a **dual collection approach** in ChromaDB: course metadata for discovery and course content for detailed search
- **Tool-based search**: AI uses function calling to decide when and how to search, rather than always searching
- **Course resolution**: Fuzzy matching allows users to reference courses by partial names
- **Static file serving**: Frontend files are served with no-cache headers for development
- **Session-based conversations**: Each user session maintains independent conversation history

## Data Storage

- **ChromaDB**: Persistent vector storage in `backend/chroma_db/`
- **Course documents**: Source documents in `docs/` folder
- **Embedding model**: `all-MiniLM-L6-v2` (downloaded automatically)
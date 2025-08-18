import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add parent directory to Python path for imports (backend modules)
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from ai_generator import AIGenerator
from config import Config
from models import Course, CourseChunk, Lesson
from rag_system import RAGSystem
from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager
from vector_store import SearchResults, VectorStore


@pytest.fixture
def mock_config():
    """Mock configuration with test values"""
    config = Mock(spec=Config)
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_RESULTS = 5  # Fixed value instead of 0
    config.MAX_HISTORY = 2
    config.CHROMA_PATH = "./test_chroma_db"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    return config


@pytest.fixture
def mock_vector_store():
    """Mock vector store with controlled responses"""
    mock_store = Mock(spec=VectorStore)

    # Mock successful search results
    mock_store.search.return_value = SearchResults(
        documents=["Test content from course 1", "More content from course 1"],
        metadata=[
            {"course_title": "Test Course", "lesson_number": 1, "chunk_index": 0},
            {"course_title": "Test Course", "lesson_number": 2, "chunk_index": 1},
        ],
        distances=[0.1, 0.2],
    )

    # Mock course resolution
    mock_store._resolve_course_name.return_value = "Test Course"

    # Mock course catalog access
    mock_catalog = Mock()
    mock_catalog.get.return_value = {
        "metadatas": [
            {
                "title": "Test Course",
                "course_link": "https://example.com/course",
                "lessons_json": '[{"lesson_number": 1, "lesson_title": "Intro", "lesson_link": "https://example.com/lesson1"}]',
            }
        ]
    }
    mock_store.course_catalog = mock_catalog

    return mock_store


@pytest.fixture
def empty_search_results():
    """Empty search results for testing no-results scenarios"""
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def error_search_results():
    """Error search results for testing error scenarios"""
    return SearchResults.empty("Database connection failed")


@pytest.fixture
def sample_course():
    """Sample course data for testing"""
    lessons = [
        Lesson(
            lesson_number=1,
            title="Introduction",
            lesson_link="https://example.com/lesson1",
        ),
        Lesson(
            lesson_number=2,
            title="Advanced Topics",
            lesson_link="https://example.com/lesson2",
        ),
    ]
    return Course(
        title="Test Course",
        course_link="https://example.com/course",
        instructor="Test Instructor",
        lessons=lessons,
    )


@pytest.fixture
def sample_chunks(sample_course):
    """Sample course chunks for testing"""
    return [
        CourseChunk(
            content="This is lesson 1 content about introductory topics.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="This is lesson 2 content about advanced topics.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=1,
        ),
    ]


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic API client"""
    mock_client = Mock()

    # Mock successful response without tools
    mock_response = Mock()
    mock_response.content = [Mock(text="Test AI response")]
    mock_response.stop_reason = "end_turn"
    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_anthropic_tool_response():
    """Mock Anthropic API response with tool use"""
    mock_response = Mock()
    mock_response.stop_reason = "tool_use"

    # Mock tool use content block
    mock_tool_block = Mock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.name = "search_course_content"
    mock_tool_block.input = {"query": "test query"}
    mock_tool_block.id = "tool_123"

    mock_response.content = [mock_tool_block]
    return mock_response


@pytest.fixture
def temp_chroma_db():
    """Temporary ChromaDB directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


# API Testing Fixtures


@pytest.fixture
def mock_rag_system():
    """Mock RAG system for API testing"""
    mock_rag = Mock(spec=RAGSystem)

    # Mock session manager
    mock_session_manager = Mock()
    mock_session_manager.create_session.return_value = "test-session-123"
    mock_session_manager.clear_session.return_value = None
    mock_rag.session_manager = mock_session_manager

    # Mock query response
    mock_rag.query.return_value = (
        "This is a test response about the course material.",
        ["Source 1: Test Course - Lesson 1", "Source 2: Test Course - Lesson 2"],
    )

    # Mock course analytics
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 3,
        "course_titles": ["Course 1", "Course 2", "Course 3"],
    }

    return mock_rag


@pytest.fixture
def test_app(mock_rag_system):
    """Create a test FastAPI app without static file mounting issues"""
    from typing import Any, Dict, List, Optional, Union

    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from pydantic import BaseModel

    # Create test app with same structure as main app but without static files
    app = FastAPI(title="Course Materials RAG System Test", root_path="")

    # Add middleware
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Set the mock RAG system
    app.state.rag_system = mock_rag_system

    # Pydantic models (copied from main app)
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Union[str, Dict[str, Any]]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    class ClearSessionRequest(BaseModel):
        session_id: str

    class ClearSessionResponse(BaseModel):
        success: bool
        message: str

    # API endpoints (copied from main app)
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            rag_system = app.state.rag_system
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()

            answer, sources = rag_system.query(request.query, session_id)

            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            rag_system = app.state.rag_system
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/session/clear", response_model=ClearSessionResponse)
    async def clear_session(request: ClearSessionRequest):
        try:
            rag_system = app.state.rag_system
            rag_system.session_manager.clear_session(request.session_id)
            return ClearSessionResponse(
                success=True,
                message=f"Session {request.session_id} cleared successfully",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {"message": "Course Materials RAG System API"}

    return app


@pytest.fixture
def test_client(test_app):
    """Create test client for API testing"""
    return TestClient(test_app)


@pytest.fixture
def sample_query_request():
    """Sample query request data for API testing"""
    return {"query": "What is machine learning?", "session_id": "test-session-123"}


@pytest.fixture
def sample_query_request_no_session():
    """Sample query request without session ID"""
    return {"query": "Explain neural networks"}


@pytest.fixture
def sample_clear_session_request():
    """Sample clear session request data"""
    return {"session_id": "test-session-123"}

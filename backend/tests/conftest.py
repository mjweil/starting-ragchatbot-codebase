import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
import tempfile
import shutil

# Add parent directory to Python path for imports (backend modules)
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from vector_store import VectorStore, SearchResults
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from ai_generator import AIGenerator
from rag_system import RAGSystem
from models import Course, Lesson, CourseChunk
from config import Config


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
            {"course_title": "Test Course", "lesson_number": 2, "chunk_index": 1}
        ],
        distances=[0.1, 0.2]
    )
    
    # Mock course resolution
    mock_store._resolve_course_name.return_value = "Test Course"
    
    # Mock course catalog access
    mock_catalog = Mock()
    mock_catalog.get.return_value = {
        'metadatas': [{
            'title': 'Test Course',
            'course_link': 'https://example.com/course',
            'lessons_json': '[{"lesson_number": 1, "lesson_title": "Intro", "lesson_link": "https://example.com/lesson1"}]'
        }]
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
        Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1"),
        Lesson(lesson_number=2, title="Advanced Topics", lesson_link="https://example.com/lesson2")
    ]
    return Course(
        title="Test Course",
        course_link="https://example.com/course",
        instructor="Test Instructor",
        lessons=lessons
    )


@pytest.fixture
def sample_chunks(sample_course):
    """Sample course chunks for testing"""
    return [
        CourseChunk(
            content="This is lesson 1 content about introductory topics.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0
        ),
        CourseChunk(
            content="This is lesson 2 content about advanced topics.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=1
        )
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
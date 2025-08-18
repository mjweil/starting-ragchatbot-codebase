import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add parent directory to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from models import Course, CourseChunk, Lesson
from rag_system import RAGSystem
from vector_store import SearchResults


class TestRAGSystemIntegration:
    """Integration tests for the complete RAG system"""

    def test_init(self, mock_config):
        """Test RAG system initialization"""
        with (
            patch("backend.rag_system.VectorStore"),
            patch("backend.rag_system.AIGenerator"),
            patch("backend.rag_system.DocumentProcessor"),
            patch("backend.rag_system.SessionManager"),
        ):

            rag = RAGSystem(mock_config)

            assert rag.config == mock_config
            assert hasattr(rag, "vector_store")
            assert hasattr(rag, "ai_generator")
            assert hasattr(rag, "document_processor")
            assert hasattr(rag, "session_manager")
            assert hasattr(rag, "tool_manager")
            assert hasattr(rag, "search_tool")
            assert hasattr(rag, "outline_tool")

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_without_session(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
    ):
        """Test querying without a session ID"""
        # Setup mocks
        mock_ai_instance = Mock()
        mock_ai_generator.return_value = mock_ai_instance
        mock_ai_instance.generate_response.return_value = "Test AI response"

        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = ["source1", "source2"]

        rag = RAGSystem(mock_config)
        rag.tool_manager = mock_tool_manager

        result, sources = rag.query("What is AI?")

        assert result == "Test AI response"
        assert sources == ["source1", "source2"]

        # Verify AI generator was called correctly
        mock_ai_instance.generate_response.assert_called_once()
        call_args = mock_ai_instance.generate_response.call_args[1]
        assert (
            call_args["query"]
            == "Answer this question about course materials: What is AI?"
        )
        assert call_args["conversation_history"] is None
        assert "tools" in call_args
        assert "tool_manager" in call_args

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_with_session(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
    ):
        """Test querying with session ID and conversation history"""
        # Setup session manager mock
        mock_session_instance = Mock()
        mock_session_manager.return_value = mock_session_instance
        mock_session_instance.get_conversation_history.return_value = (
            "Previous conversation"
        )

        # Setup AI generator mock
        mock_ai_instance = Mock()
        mock_ai_generator.return_value = mock_ai_instance
        mock_ai_instance.generate_response.return_value = "Contextual AI response"

        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = []

        rag = RAGSystem(mock_config)
        rag.tool_manager = mock_tool_manager

        result, sources = rag.query("Follow up question", session_id="session123")

        assert result == "Contextual AI response"

        # Verify session history was retrieved and used
        mock_session_instance.get_conversation_history.assert_called_once_with(
            "session123"
        )

        call_args = mock_ai_instance.generate_response.call_args[1]
        assert call_args["conversation_history"] == "Previous conversation"

        # Verify conversation was updated
        mock_session_instance.add_exchange.assert_called_once_with(
            "session123", "Follow up question", "Contextual AI response"
        )

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_tool_execution_flow(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
    ):
        """Test the complete flow when AI uses tools"""
        # Setup AI generator to simulate tool usage
        mock_ai_instance = Mock()
        mock_ai_generator.return_value = mock_ai_instance
        mock_ai_instance.generate_response.return_value = (
            "Response using course search results"
        )

        # Setup tool manager with sources
        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = [
            {"name": "search_course_content", "description": "Search tool"}
        ]
        mock_tool_manager.get_last_sources.return_value = [
            {"display": "Test Course - Lesson 1", "link": "https://example.com/lesson1"}
        ]

        rag = RAGSystem(mock_config)
        rag.tool_manager = mock_tool_manager

        result, sources = rag.query("Tell me about machine learning")

        assert result == "Response using course search results"
        assert len(sources) == 1
        assert sources[0]["display"] == "Test Course - Lesson 1"

        # Verify tool definitions were provided to AI
        call_args = mock_ai_instance.generate_response.call_args[1]
        assert call_args["tools"] == [
            {"name": "search_course_content", "description": "Search tool"}
        ]
        assert call_args["tool_manager"] == mock_tool_manager

        # Verify sources were retrieved and reset
        mock_tool_manager.get_last_sources.assert_called_once()
        mock_tool_manager.reset_sources.assert_called_once()

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_add_course_document_success(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
        sample_course,
        sample_chunks,
    ):
        """Test successful course document addition"""
        # Setup document processor mock
        mock_doc_instance = Mock()
        mock_doc_processor.return_value = mock_doc_instance
        mock_doc_instance.process_course_document.return_value = (
            sample_course,
            sample_chunks,
        )

        # Setup vector store mock
        mock_store_instance = Mock()
        mock_vector_store.return_value = mock_store_instance

        rag = RAGSystem(mock_config)

        course, chunk_count = rag.add_course_document("/path/to/course.txt")

        assert course == sample_course
        assert chunk_count == len(sample_chunks)

        # Verify document processing
        mock_doc_instance.process_course_document.assert_called_once_with(
            "/path/to/course.txt"
        )

        # Verify vector store operations
        mock_store_instance.add_course_metadata.assert_called_once_with(sample_course)
        mock_store_instance.add_course_content.assert_called_once_with(sample_chunks)

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_add_course_document_error(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
    ):
        """Test course document addition with error"""
        # Setup document processor to raise exception
        mock_doc_instance = Mock()
        mock_doc_processor.return_value = mock_doc_instance
        mock_doc_instance.process_course_document.side_effect = Exception(
            "File not found"
        )

        rag = RAGSystem(mock_config)

        course, chunk_count = rag.add_course_document("/invalid/path.txt")

        assert course is None
        assert chunk_count == 0

    @patch("rag_system.os.path.exists")
    @patch("rag_system.os.listdir")
    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_add_course_folder_success(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_exists,
        mock_listdir,
        mock_config,
        sample_course,
        sample_chunks,
    ):
        """Test successful course folder addition"""
        # Setup filesystem mocks
        mock_exists.return_value = True
        mock_listdir.return_value = ["course1.txt", "course2.pdf", "readme.md"]

        # Setup document processor
        mock_doc_instance = Mock()
        mock_doc_processor.return_value = mock_doc_instance
        mock_doc_instance.process_course_document.return_value = (
            sample_course,
            sample_chunks,
        )

        # Setup vector store
        mock_store_instance = Mock()
        mock_vector_store.return_value = mock_store_instance
        mock_store_instance.get_existing_course_titles.return_value = (
            []
        )  # No existing courses

        rag = RAGSystem(mock_config)

        with (
            patch("backend.rag_system.os.path.isfile", return_value=True),
            patch(
                "backend.rag_system.os.path.join", side_effect=lambda a, b: f"{a}/{b}"
            ),
        ):

            total_courses, total_chunks = rag.add_course_folder("/path/to/courses")

        assert total_courses == 2  # Only .txt and .pdf files should be processed
        assert total_chunks == len(sample_chunks) * 2

        # Verify document processor was called for valid files
        assert mock_doc_instance.process_course_document.call_count == 2

    @patch("rag_system.os.path.exists")
    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_add_course_folder_not_exists(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_exists,
        mock_config,
    ):
        """Test course folder addition when folder doesn't exist"""
        mock_exists.return_value = False

        rag = RAGSystem(mock_config)

        total_courses, total_chunks = rag.add_course_folder("/nonexistent/path")

        assert total_courses == 0
        assert total_chunks == 0

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_get_course_analytics(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
    ):
        """Test getting course analytics"""
        # Setup vector store mock
        mock_store_instance = Mock()
        mock_vector_store.return_value = mock_store_instance
        mock_store_instance.get_course_count.return_value = 3
        mock_store_instance.get_existing_course_titles.return_value = [
            "Course 1",
            "Course 2",
            "Course 3",
        ]

        rag = RAGSystem(mock_config)

        analytics = rag.get_course_analytics()

        assert analytics["total_courses"] == 3
        assert analytics["course_titles"] == ["Course 1", "Course 2", "Course 3"]

        # Verify vector store methods were called
        mock_store_instance.get_course_count.assert_called_once()
        mock_store_instance.get_existing_course_titles.assert_called_once()

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_with_max_results_zero(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
    ):
        """Test that the system fails gracefully when MAX_RESULTS is 0"""
        # This tests the critical bug we identified
        mock_config.MAX_RESULTS = 0

        # Setup mocks
        mock_ai_instance = Mock()
        mock_ai_generator.return_value = mock_ai_instance
        mock_ai_instance.generate_response.return_value = "No results found"

        # Setup search tool that will get empty results due to MAX_RESULTS=0
        mock_store_instance = Mock()
        mock_vector_store.return_value = mock_store_instance
        mock_store_instance.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = []

        rag = RAGSystem(mock_config)
        rag.tool_manager = mock_tool_manager

        result, sources = rag.query("What is machine learning?")

        # The system should still work, but with no useful results
        assert result == "No results found"
        assert sources == []

    @patch("rag_system.VectorStore")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_error_handling_in_query(
        self,
        mock_session_manager,
        mock_doc_processor,
        mock_ai_generator,
        mock_vector_store,
        mock_config,
    ):
        """Test error handling during query processing"""
        # Setup AI generator to raise exception
        mock_ai_instance = Mock()
        mock_ai_generator.return_value = mock_ai_instance
        mock_ai_instance.generate_response.side_effect = Exception("API Error")

        rag = RAGSystem(mock_config)

        # The query method doesn't have explicit error handling, so exception should propagate
        with pytest.raises(Exception, match="API Error"):
            rag.query("Test query")

    def test_real_config_max_results_issue(self):
        """Test that identifies the real configuration issue"""
        # This test verifies our root cause analysis
        from config import config

        # This should fail if MAX_RESULTS is still 0
        if hasattr(config, "MAX_RESULTS"):
            assert (
                config.MAX_RESULTS != 0
            ), "MAX_RESULTS should not be 0 - this causes empty search results"

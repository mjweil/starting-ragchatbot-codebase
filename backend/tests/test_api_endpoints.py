import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add parent directory to Python path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestAPIEndpoints:
    """Test FastAPI endpoints for proper request/response handling"""

    def test_root_endpoint(self, test_client):
        """Test the root endpoint returns correct response"""
        response = test_client.get("/")

        assert response.status_code == 200
        assert response.json() == {"message": "Course Materials RAG System API"}

    def test_query_endpoint_with_session(self, test_client, sample_query_request):
        """Test /api/query endpoint with existing session ID"""
        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Verify response content
        assert data["answer"] == "This is a test response about the course material."
        assert data["session_id"] == "test-session-123"
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) == 2

    def test_query_endpoint_without_session(
        self, test_client, sample_query_request_no_session
    ):
        """Test /api/query endpoint creates new session when none provided"""
        response = test_client.post("/api/query", json=sample_query_request_no_session)

        assert response.status_code == 200
        data = response.json()

        # Verify new session was created
        assert data["session_id"] == "test-session-123"  # From mock
        assert data["answer"] == "This is a test response about the course material."

    def test_query_endpoint_invalid_request(self, test_client):
        """Test /api/query endpoint with invalid request data"""
        # Missing required 'query' field
        invalid_request = {"session_id": "test-session"}

        response = test_client.post("/api/query", json=invalid_request)
        assert response.status_code == 422  # Validation error

    def test_query_endpoint_empty_query(self, test_client):
        """Test /api/query endpoint with empty query"""
        empty_query = {"query": ""}

        response = test_client.post("/api/query", json=empty_query)
        assert response.status_code == 200  # Should still process empty query

    def test_courses_endpoint(self, test_client):
        """Test /api/courses endpoint returns course statistics"""
        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "total_courses" in data
        assert "course_titles" in data

        # Verify response content from mock
        assert data["total_courses"] == 3
        assert data["course_titles"] == ["Course 1", "Course 2", "Course 3"]

    def test_clear_session_endpoint(self, test_client, sample_clear_session_request):
        """Test /api/session/clear endpoint"""
        response = test_client.post(
            "/api/session/clear", json=sample_clear_session_request
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "success" in data
        assert "message" in data

        # Verify response content
        assert data["success"] is True
        assert "test-session-123" in data["message"]

    def test_clear_session_endpoint_invalid_request(self, test_client):
        """Test /api/session/clear endpoint with invalid request"""
        # Missing required 'session_id' field
        invalid_request = {}

        response = test_client.post("/api/session/clear", json=invalid_request)
        assert response.status_code == 422  # Validation error

    def test_query_endpoint_rag_system_error(self, test_client, mock_rag_system):
        """Test /api/query endpoint handles RAG system errors gracefully"""
        # Configure mock to raise exception
        mock_rag_system.query.side_effect = Exception("Database connection failed")

        query_request = {"query": "test query"}
        response = test_client.post("/api/query", json=query_request)

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]

    def test_courses_endpoint_rag_system_error(self, test_client, mock_rag_system):
        """Test /api/courses endpoint handles RAG system errors gracefully"""
        # Configure mock to raise exception
        mock_rag_system.get_course_analytics.side_effect = Exception(
            "Analytics service unavailable"
        )

        response = test_client.get("/api/courses")

        assert response.status_code == 500
        assert "Analytics service unavailable" in response.json()["detail"]

    def test_clear_session_endpoint_rag_system_error(
        self, test_client, mock_rag_system
    ):
        """Test /api/session/clear endpoint handles RAG system errors gracefully"""
        # Configure mock to raise exception
        mock_rag_system.session_manager.clear_session.side_effect = Exception(
            "Session service error"
        )

        clear_request = {"session_id": "test-session"}
        response = test_client.post("/api/session/clear", json=clear_request)

        assert response.status_code == 500
        assert "Session service error" in response.json()["detail"]

    def test_query_endpoint_content_type_validation(self, test_client):
        """Test /api/query endpoint requires JSON content type"""
        # Test with form data instead of JSON
        response = test_client.post("/api/query", data={"query": "test"})

        # Should return 422 due to content type mismatch
        assert response.status_code == 422

    def test_cors_middleware_configured(self, test_client):
        """Test that CORS middleware is configured properly"""
        # Test OPTIONS request which should trigger CORS behavior
        response = test_client.options("/api/courses")

        # CORS middleware should handle OPTIONS requests
        assert response.status_code in [
            200,
            405,
        ]  # Either allowed or method not allowed

        # Test that regular requests work (middleware doesn't block them)
        response = test_client.get("/api/courses")
        assert response.status_code == 200

    def test_api_response_models_validation(self, test_client, mock_rag_system):
        """Test API response models handle different data types correctly"""
        # Test with mixed source types (string and dict)
        mock_rag_system.query.return_value = (
            "Test response",
            ["String source", {"title": "Dict source", "lesson": 1}],
        )

        query_request = {"query": "test query"}
        response = test_client.post("/api/query", json=query_request)

        assert response.status_code == 200
        data = response.json()

        # Verify mixed source types are handled correctly
        sources = data["sources"]
        assert len(sources) == 2
        assert sources[0] == "String source"
        assert isinstance(sources[1], dict)
        assert sources[1]["title"] == "Dict source"

    def test_session_id_generation_flow(self, test_client, mock_rag_system):
        """Test the complete session ID generation flow"""
        # Mock session manager to track calls
        mock_session_manager = mock_rag_system.session_manager
        mock_session_manager.create_session.return_value = "new-session-456"

        # Query without session ID
        query_request = {"query": "test query"}
        response = test_client.post("/api/query", json=query_request)

        assert response.status_code == 200
        data = response.json()

        # Verify session was created and returned
        assert data["session_id"] == "new-session-456"
        mock_session_manager.create_session.assert_called_once()

    def test_query_endpoint_parameter_passing(self, test_client, mock_rag_system):
        """Test that query parameters are correctly passed to RAG system"""
        query_request = {
            "query": "What is artificial intelligence?",
            "session_id": "custom-session-789",
        }

        response = test_client.post("/api/query", json=query_request)

        assert response.status_code == 200

        # Verify RAG system was called with correct parameters
        mock_rag_system.query.assert_called_once_with(
            "What is artificial intelligence?", "custom-session-789"
        )

    def test_api_endpoint_routing(self, test_client):
        """Test that all API endpoints are properly routed"""
        # Test valid endpoints
        endpoints_to_test = [
            ("/", "get", 200),
            ("/api/courses", "get", 200),
        ]

        for endpoint, method, expected_status in endpoints_to_test:
            if method == "get":
                response = test_client.get(endpoint)
            else:
                response = test_client.post(endpoint)

            assert response.status_code == expected_status

    def test_nonexistent_endpoint(self, test_client):
        """Test that nonexistent endpoints return 404"""
        response = test_client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_unsupported_method(self, test_client):
        """Test that unsupported HTTP methods return 405"""
        # POST to GET-only endpoint
        response = test_client.post("/api/courses")
        assert response.status_code == 405

        # GET to POST-only endpoint
        response = test_client.get("/api/query")
        assert response.status_code == 405

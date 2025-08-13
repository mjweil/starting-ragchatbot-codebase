import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add parent directory to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test CourseSearchTool functionality"""
    
    def test_get_tool_definition(self, mock_vector_store):
        """Test that tool definition is properly formatted"""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()
        
        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["required"] == ["query"]
        assert "query" in definition["input_schema"]["properties"]
        assert "course_name" in definition["input_schema"]["properties"]
        assert "lesson_number" in definition["input_schema"]["properties"]
    
    def test_execute_successful_search(self, mock_vector_store):
        """Test successful search with results"""
        tool = CourseSearchTool(mock_vector_store)
        
        result = tool.execute("test query")
        
        # Verify vector store was called correctly
        mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name=None,
            lesson_number=None
        )
        
        # Verify result contains formatted content
        assert "[Test Course - Lesson 1]" in result
        assert "[Test Course - Lesson 2]" in result
        assert "Test content from course 1" in result
        assert "More content from course 1" in result
        
        # Verify sources were stored
        assert len(tool.last_sources) == 2
        assert tool.last_sources[0]["display"] == "Test Course - Lesson 1"
        assert tool.last_sources[1]["display"] == "Test Course - Lesson 2"
    
    def test_execute_with_filters(self, mock_vector_store):
        """Test search with course and lesson filters"""
        tool = CourseSearchTool(mock_vector_store)
        
        result = tool.execute("test query", course_name="Test Course", lesson_number=1)
        
        mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name="Test Course",
            lesson_number=1
        )
    
    def test_execute_empty_results(self, mock_vector_store, empty_search_results):
        """Test handling of empty search results"""
        mock_vector_store.search.return_value = empty_search_results
        tool = CourseSearchTool(mock_vector_store)
        
        result = tool.execute("test query")
        
        assert "No relevant content found" in result
        assert tool.last_sources == []
    
    def test_execute_empty_results_with_filters(self, mock_vector_store, empty_search_results):
        """Test empty results with filter information"""
        mock_vector_store.search.return_value = empty_search_results
        tool = CourseSearchTool(mock_vector_store)
        
        result = tool.execute("test query", course_name="Test Course", lesson_number=1)
        
        assert "No relevant content found in course 'Test Course' in lesson 1" in result
    
    def test_execute_with_error(self, mock_vector_store, error_search_results):
        """Test handling of search errors"""
        mock_vector_store.search.return_value = error_search_results
        tool = CourseSearchTool(mock_vector_store)
        
        result = tool.execute("test query")
        
        assert "Database connection failed" in result
    
    def test_format_results_with_links(self, mock_vector_store):
        """Test result formatting includes links when available"""
        # Mock get_lesson_link to return a URL
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson1"
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("test query")
        
        # Verify sources contain links
        assert len(tool.last_sources) == 2
        assert tool.last_sources[0]["link"] is not None


class TestCourseOutlineTool:
    """Test CourseOutlineTool functionality"""
    
    def test_get_tool_definition(self, mock_vector_store):
        """Test that tool definition is properly formatted"""
        tool = CourseOutlineTool(mock_vector_store)
        definition = tool.get_tool_definition()
        
        assert definition["name"] == "get_course_outline"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["required"] == ["course_name"]
        assert "course_name" in definition["input_schema"]["properties"]
    
    def test_execute_successful_outline(self, mock_vector_store):
        """Test successful course outline retrieval"""
        tool = CourseOutlineTool(mock_vector_store)
        
        result = tool.execute("Test Course")
        
        # Verify course name was resolved
        mock_vector_store._resolve_course_name.assert_called_once_with("Test Course")
        
        # Verify course catalog was queried
        mock_vector_store.course_catalog.get.assert_called_once_with(ids=["Test Course"])
        
        # Verify result contains course information
        assert "Course: Test Course" in result
        assert "Course Link: https://example.com/course" in result
        assert "Lessons (1 total):" in result
        assert "Lesson 1: Intro" in result
        
        # Verify sources were stored
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["display"] == "Test Course"
        assert tool.last_sources[0]["link"] == "https://example.com/course"
    
    def test_execute_course_not_found(self, mock_vector_store):
        """Test handling of course not found"""
        mock_vector_store._resolve_course_name.return_value = None
        tool = CourseOutlineTool(mock_vector_store)
        
        result = tool.execute("Nonexistent Course")
        
        assert "No course found matching 'Nonexistent Course'" in result
    
    def test_execute_no_metadata(self, mock_vector_store):
        """Test handling of missing course metadata"""
        mock_vector_store.course_catalog.get.return_value = {'metadatas': []}
        tool = CourseOutlineTool(mock_vector_store)
        
        result = tool.execute("Test Course")
        
        assert "No course metadata found" in result
    
    def test_execute_no_lessons(self, mock_vector_store):
        """Test handling of course without lessons"""
        mock_vector_store.course_catalog.get.return_value = {
            'metadatas': [{
                'title': 'Test Course',
                'course_link': 'https://example.com/course',
                'lessons_json': None
            }]
        }
        tool = CourseOutlineTool(mock_vector_store)
        
        result = tool.execute("Test Course")
        
        assert "No lesson information available" in result
    
    def test_execute_with_exception(self, mock_vector_store):
        """Test handling of exceptions during outline retrieval"""
        mock_vector_store.course_catalog.get.side_effect = Exception("DB Error")
        tool = CourseOutlineTool(mock_vector_store)
        
        result = tool.execute("Test Course")
        
        assert "Error retrieving course outline" in result
        assert "DB Error" in result


class TestToolManager:
    """Test ToolManager functionality"""
    
    def test_register_tool(self, mock_vector_store):
        """Test tool registration"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        
        manager.register_tool(search_tool)
        
        assert "search_course_content" in manager.tools
        assert manager.tools["search_course_content"] == search_tool
    
    def test_get_tool_definitions(self, mock_vector_store):
        """Test getting all tool definitions"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        outline_tool = CourseOutlineTool(mock_vector_store)
        
        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)
        
        definitions = manager.get_tool_definitions()
        
        assert len(definitions) == 2
        tool_names = [d["name"] for d in definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names
    
    def test_execute_tool(self, mock_vector_store):
        """Test tool execution through manager"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)
        
        result = manager.execute_tool("search_course_content", query="test")
        
        # Verify the tool was executed
        assert "[Test Course - Lesson 1]" in result
    
    def test_execute_nonexistent_tool(self, mock_vector_store):
        """Test execution of non-registered tool"""
        manager = ToolManager()
        
        result = manager.execute_tool("nonexistent_tool", query="test")
        
        assert "Tool 'nonexistent_tool' not found" in result
    
    def test_get_last_sources(self, mock_vector_store):
        """Test getting sources from last search"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)
        
        # Execute search to populate sources
        manager.execute_tool("search_course_content", query="test")
        
        sources = manager.get_last_sources()
        assert len(sources) == 2
        assert sources[0]["display"] == "Test Course - Lesson 1"
    
    def test_reset_sources(self, mock_vector_store):
        """Test resetting sources from all tools"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)
        
        # Execute search to populate sources
        manager.execute_tool("search_course_content", query="test")
        assert len(manager.get_last_sources()) == 2
        
        # Reset sources
        manager.reset_sources()
        assert len(manager.get_last_sources()) == 0
    
    def test_register_tool_without_name(self, mock_vector_store):
        """Test registering tool without proper name"""
        manager = ToolManager()
        
        # Create a mock tool with no name in definition
        mock_tool = Mock()
        mock_tool.get_tool_definition.return_value = {"description": "test"}
        
        with pytest.raises(ValueError, match="Tool must have a 'name'"):
            manager.register_tool(mock_tool)
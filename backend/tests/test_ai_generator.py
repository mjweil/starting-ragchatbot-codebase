import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add parent directory to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from ai_generator import AIGenerator


class TestAIGenerator:
    """Test AIGenerator functionality"""

    def test_init(self):
        """Test AIGenerator initialization"""
        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")

        assert generator.model == "claude-sonnet-4-20250514"
        assert generator.base_params["model"] == "claude-sonnet-4-20250514"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_simple(self, mock_anthropic_class):
        """Test simple response generation without tools"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Setup mock response
        mock_response = Mock()
        mock_response.content = [Mock(text="This is a test response")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response("What is AI?")

        assert result == "This is a test response"

        # Verify API call
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args[1]
        assert call_args["model"] == "claude-sonnet-4-20250514"
        assert call_args["messages"][0]["content"] == "What is AI?"
        assert AIGenerator.SYSTEM_PROMPT in call_args["system"]

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_history(self, mock_anthropic_class):
        """Test response generation with conversation history"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [Mock(text="Response with context")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "Follow up question", conversation_history="Previous conversation context"
        )

        assert result == "Response with context"

        # Verify history was included in system prompt
        call_args = mock_client.messages.create.call_args[1]
        assert "Previous conversation context" in call_args["system"]

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tools_no_use(self, mock_anthropic_class):
        """Test response generation with tools available but not used"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [Mock(text="Direct response without tools")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response

        mock_tools = [{"name": "test_tool", "description": "Test tool"}]
        mock_tool_manager = Mock()

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "What is AI?", tools=mock_tools, tool_manager=mock_tool_manager
        )

        assert result == "Direct response without tools"

        # Verify tools were provided in API call
        call_args = mock_client.messages.create.call_args[1]
        assert call_args["tools"] == mock_tools
        assert call_args["tool_choice"] == {"type": "auto"}

        # Tool manager should not be called
        mock_tool_manager.execute_tool.assert_not_called()

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tool_use(self, mock_anthropic_class):
        """Test response generation with tool execution"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First response triggers tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.input = {"query": "test query"}
        mock_tool_block.id = "tool_123"

        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"

        # Final response after tool execution
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Response using tool results")]

        # Configure mock client to return different responses
        mock_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response,
        ]

        # Setup mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool execution result"

        mock_tools = [{"name": "search_course_content", "description": "Search tool"}]

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "Search for information about AI",
            tools=mock_tools,
            tool_manager=mock_tool_manager,
        )

        assert result == "Response using tool results"

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="test query"
        )

        # Verify two API calls were made
        assert mock_client.messages.create.call_count == 2

    @patch("ai_generator.anthropic.Anthropic")
    def test_handle_tool_execution_multiple_tools(self, mock_anthropic_class):
        """Test handling multiple tool calls in one response"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Create multiple tool blocks
        mock_tool_block1 = Mock()
        mock_tool_block1.type = "tool_use"
        mock_tool_block1.name = "search_course_content"
        mock_tool_block1.input = {"query": "test query 1"}
        mock_tool_block1.id = "tool_123"

        mock_tool_block2 = Mock()
        mock_tool_block2.type = "tool_use"
        mock_tool_block2.name = "get_course_outline"
        mock_tool_block2.input = {"course_name": "Test Course"}
        mock_tool_block2.id = "tool_456"

        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block1, mock_tool_block2]
        mock_initial_response.stop_reason = "tool_use"

        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Combined tool results")]

        mock_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response,
        ]

        # Setup mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = ["Search result", "Outline result"]

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "Complex query", tools=[], tool_manager=mock_tool_manager
        )

        assert result == "Combined tool results"

        # Verify both tools were executed
        assert mock_tool_manager.execute_tool.call_count == 2
        mock_tool_manager.execute_tool.assert_any_call(
            "search_course_content", query="test query 1"
        )
        mock_tool_manager.execute_tool.assert_any_call(
            "get_course_outline", course_name="Test Course"
        )

    @patch("ai_generator.anthropic.Anthropic")
    def test_handle_tool_execution_message_flow(self, mock_anthropic_class):
        """Test proper message flow during tool execution"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Setup tool use scenario
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "test_tool"
        mock_tool_block.input = {"param": "value"}
        mock_tool_block.id = "tool_123"

        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"

        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Final response")]

        mock_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response,
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "Initial query", tools=[], tool_manager=mock_tool_manager
        )

        # Verify final API call structure
        final_call_args = mock_client.messages.create.call_args_list[1][1]
        messages = final_call_args["messages"]

        # Should have: initial user message, assistant tool use, tool results
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Initial query"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"
        assert messages[2]["content"][0]["tool_use_id"] == "tool_123"
        assert messages[2]["content"][0]["content"] == "Tool result"

    @patch("ai_generator.anthropic.Anthropic")
    def test_api_error_handling(self, mock_anthropic_class):
        """Test handling of API errors"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Simulate API error
        mock_client.messages.create.side_effect = Exception("API Error")

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")

        # Our new implementation catches exceptions and returns error messages
        result = generator.generate_response("Test query")
        assert "encountered an error while processing your request" in result
        assert "API Error" in result

    def test_system_prompt_content(self):
        """Test that system prompt contains expected guidance"""
        prompt = AIGenerator.SYSTEM_PROMPT

        # Check for key components
        assert "course materials" in prompt.lower()
        assert "search_course_content" in prompt
        assert "get_course_outline" in prompt
        assert "tool" in prompt.lower()
        assert "brief" in prompt.lower() or "concise" in prompt.lower()

    @patch("ai_generator.anthropic.Anthropic")
    def test_tool_execution_without_manager(self, mock_anthropic_class):
        """Test tool use response when no tool manager provided"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "test_tool"

        mock_response = Mock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_client.messages.create.return_value = mock_response

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")

        # Without tool_manager, it should go through loop and hit fallback
        result = generator.generate_response("Test", tools=[], tool_manager=None)
        assert "unable to complete the request" in result

    @patch("ai_generator.anthropic.Anthropic")
    def test_sequential_tool_calling_two_rounds(self, mock_anthropic_class):
        """Test successful two-round sequential tool calling"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Round 1: Tool use
        mock_tool_block1 = Mock()
        mock_tool_block1.type = "tool_use"
        mock_tool_block1.name = "get_course_outline"
        mock_tool_block1.input = {"course_name": "MCP"}
        mock_tool_block1.id = "tool_123"

        mock_response1 = Mock()
        mock_response1.content = [mock_tool_block1]
        mock_response1.stop_reason = "tool_use"

        # Round 1 follow-up: Requests more tools
        mock_tool_block2 = Mock()
        mock_tool_block2.type = "tool_use"
        mock_tool_block2.name = "search_course_content"
        mock_tool_block2.input = {"query": "lesson 4", "course_name": "MCP"}
        mock_tool_block2.id = "tool_456"

        mock_response2 = Mock()
        mock_response2.content = [mock_tool_block2]
        mock_response2.stop_reason = "tool_use"

        # Round 2 follow-up: Final response
        mock_response3 = Mock()
        mock_response3.content = [Mock(text="Final response with comprehensive info")]
        mock_response3.stop_reason = "end_turn"

        # Configure mock to return responses in sequence
        mock_client.messages.create.side_effect = [
            mock_response1,  # Initial tool use
            mock_response2,  # Round 1 follow-up requesting more tools
            mock_response3,  # Round 2 follow-up final response
        ]

        # Setup tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Course outline result",
            "Search content result",
        ]

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "Tell me about lesson 4 of MCP course",
            tools=[{"name": "get_course_outline"}, {"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        assert result == "Final response with comprehensive info"

        # Verify both tools were executed
        assert mock_tool_manager.execute_tool.call_count == 2
        mock_tool_manager.execute_tool.assert_any_call(
            "get_course_outline", course_name="MCP"
        )
        mock_tool_manager.execute_tool.assert_any_call(
            "search_course_content", query="lesson 4", course_name="MCP"
        )

        # Verify 3 API calls were made (round 1 initial + follow-up, round 2 follow-up)
        assert mock_client.messages.create.call_count == 3

    @patch("ai_generator.anthropic.Anthropic")
    def test_sequential_tool_calling_early_termination(self, mock_anthropic_class):
        """Test early termination when Claude is satisfied after first round"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Round 1: Tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "get_course_outline"
        mock_tool_block.input = {"course_name": "MCP"}
        mock_tool_block.id = "tool_123"

        mock_response1 = Mock()
        mock_response1.content = [mock_tool_block]
        mock_response1.stop_reason = "tool_use"

        # Round 1 follow-up: Final response (no more tools)
        mock_response2 = Mock()
        mock_response2.content = [Mock(text="Complete response after first tool")]
        mock_response2.stop_reason = "end_turn"

        mock_client.messages.create.side_effect = [mock_response1, mock_response2]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Course outline result"

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "What is the MCP course about?",
            tools=[{"name": "get_course_outline"}],
            tool_manager=mock_tool_manager,
        )

        assert result == "Complete response after first tool"

        # Verify only one tool execution
        mock_tool_manager.execute_tool.assert_called_once_with(
            "get_course_outline", course_name="MCP"
        )

        # Verify only 2 API calls (round 1 initial + follow-up, no round 2)
        assert mock_client.messages.create.call_count == 2

    @patch("ai_generator.anthropic.Anthropic")
    def test_sequential_tool_calling_max_rounds_reached(self, mock_anthropic_class):
        """Test termination when max rounds (2) is reached"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Create mock responses that always want more tools for round 1 & 2
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.input = {"query": "test"}
        mock_tool_block.id = "tool_123"

        mock_tool_response = Mock()
        mock_tool_response.content = [mock_tool_block]
        mock_tool_response.stop_reason = "tool_use"

        # Final response for round 2 after tools
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Final response after max rounds")]
        mock_final_response.stop_reason = "end_turn"

        # Mock API calls: round1 tool -> round2 tool -> final response
        mock_client.messages.create.side_effect = [
            mock_tool_response,  # Round 1
            mock_tool_response,  # Round 2
            mock_final_response,  # Final response after max rounds
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "Complex query requiring many tools",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Should terminate after max rounds and return final response
        assert result == "Final response after max rounds"

        # Should have executed tools for both rounds
        assert mock_tool_manager.execute_tool.call_count == 2

    @patch("ai_generator.anthropic.Anthropic")
    def test_sequential_tool_calling_error_in_round_two(self, mock_anthropic_class):
        """Test error handling when second round fails"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Round 1 successful
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "get_course_outline"
        mock_tool_block.input = {"course_name": "MCP"}
        mock_tool_block.id = "tool_123"

        mock_response1 = Mock()
        mock_response1.content = [mock_tool_block]
        mock_response1.stop_reason = "tool_use"

        # Round 1 follow-up requesting more tools
        mock_response2 = Mock()
        mock_response2.content = [mock_tool_block]  # Reuse for simplicity
        mock_response2.stop_reason = "tool_use"

        # Round 2 fails
        mock_client.messages.create.side_effect = [
            mock_response1,
            mock_response2,
            Exception("API Error in round 2"),
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        generator = AIGenerator("test-api-key", "claude-sonnet-4-20250514")
        result = generator.generate_response(
            "Complex query",
            tools=[{"name": "get_course_outline"}],
            tool_manager=mock_tool_manager,
        )

        # Should return graceful error message for later round failure
        assert "gathered some information but encountered an error" in result

    def test_system_prompt_sequential_guidance(self):
        """Test that system prompt includes sequential tool calling guidance"""
        prompt = AIGenerator.SYSTEM_PROMPT

        # Check for sequential tool calling guidance
        assert "Sequential tool usage" in prompt
        assert "2 rounds" in prompt
        assert "Strategic tool combinations" in prompt
        # Should no longer have the old restriction
        assert "One tool call per query maximum" not in prompt

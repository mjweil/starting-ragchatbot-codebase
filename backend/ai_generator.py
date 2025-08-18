from typing import Any, Dict, List, Optional

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search tools for course information.

Tool Usage Guidelines:
- **Course outline/structure questions**: Use the get_course_outline tool to retrieve course title, course link, and complete lesson lists
- **Specific course content questions**: Use the search_course_content tool for detailed educational materials
- **Sequential tool usage**: You can make up to 2 rounds of tool calls to gather comprehensive information
- **Strategic tool combinations**: Use get_course_outline first to understand structure, then search_course_content for specific details when needed
- Synthesize tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Response Protocol for Outline Queries:
- When using get_course_outline tool, always include:
  - Course title
  - Course link (if available)
  - Complete lesson list with lesson numbers and titles
- **Course-specific questions**: Use appropriate tool first, then answer
- **General knowledge questions**: Answer using existing knowledge without using tools
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the outline tool"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to 2 sequential rounds of tool calling.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize conversation state for sequential rounds
        messages = [{"role": "user", "content": query}]
        max_rounds = 2

        # Sequential tool calling loop (up to 2 rounds)
        for current_round in range(1, max_rounds + 1):
            # Add round context to system prompt for guidance
            round_system_content = (
                f"{system_content}\n\n[Round {current_round} of {max_rounds}]"
            )

            # Prepare API call parameters
            api_params = {
                **self.base_params,
                "messages": messages.copy(),
                "system": round_system_content,
            }

            # Add tools if available
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            try:
                # Get response from Claude
                response = self.client.messages.create(**api_params)

                # Handle tool execution if needed
                if response.stop_reason == "tool_use" and tool_manager:
                    # Execute tools and get results
                    messages.append({"role": "assistant", "content": response.content})

                    # Execute all tool calls and collect results
                    tool_results = []
                    for content_block in response.content:
                        if content_block.type == "tool_use":
                            try:
                                tool_result = tool_manager.execute_tool(
                                    content_block.name, **content_block.input
                                )
                                tool_results.append(
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": content_block.id,
                                        "content": tool_result,
                                    }
                                )
                            except Exception as e:
                                tool_results.append(
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": content_block.id,
                                        "content": f"Error executing tool: {str(e)}",
                                    }
                                )

                    if tool_results:
                        # tool_results is a list of tool result dicts, which is the correct format for Anthropic API
                        messages.append({"role": "user", "content": tool_results})  # type: ignore

                    # If this is the last round, get final response without tools
                    if current_round >= max_rounds:
                        final_params = {
                            **self.base_params,
                            "messages": messages.copy(),
                            "system": round_system_content,
                        }

                        try:
                            final_response = self.client.messages.create(**final_params)
                            return final_response.content[0].text
                        except Exception as e:
                            return "I gathered some information but encountered an error in final processing."

                    # Continue to next round
                    continue
                else:
                    # Handle case where tools are requested but no tool_manager provided
                    if response.stop_reason == "tool_use":
                        return "I was unable to complete the request within the allowed rounds."
                    # Direct response without tools, return immediately
                    return response.content[0].text

            except Exception as e:
                # Handle API errors gracefully
                if current_round == 1:
                    # First round failure - return error message
                    return f"I'm sorry, I encountered an error while processing your request: {str(e)}"
                else:
                    # Later round failure - return best effort from previous round
                    return "I gathered some information but encountered an error in follow-up analysis. Please try rephrasing your question."

        # Fallback - should not reach here due to loop logic, but safety net
        return "I was unable to complete the request within the allowed rounds."

"""Agent brain using Gemini API function calling."""
import logging
from typing import Any, Callable

from google.genai import types

from app.llm import get_gemini
from app.config import get_settings
from app.tools import (
    search_products,
    get_product_details,
    check_stock,
    generate_marketing_description,
)

log = logging.getLogger("app.agent")
settings = get_settings()

# Registry of tools the agent can use
AVAILABLE_TOOLS = [
    search_products,
    get_product_details,
    check_stock,
    generate_marketing_description,
]

# Map tool names to their actual Python functions
TOOL_MAP: dict[str, Callable] = {
    f.__name__: f for f in AVAILABLE_TOOLS
}

async def run_agent(
    user_message: str, 
    conversation_history: list[dict[str, str]] | None = None,
    max_iterations: int = 5
) -> dict[str, Any]:
    """Run the ReAct loop using Gemini's function calling via Chat."""
    client = get_gemini()
    
    system_prompt = (
        "You are an AI-powered, friendly e-commerce sales assistant.\n"
        "Your tasks: Understand customer requests, search for products, check stock, and offer the best options to the customer.\n"
        "Always use the appropriate tools based on the customer's criteria (budget, category, etc.).\n"
        "Interpret the results from the tools and respond to the customer in a natural, helpful, and sales-oriented tone.\n"
        "Think step-by-step: 1. What does the user want? 2. Which tool should I use? 3. How should I present the data?\n"
        "Only answer based on the results from your tools. Do not hallucinate information."
    )
    
    # 1. Initialize history for the Chat object
    history = []
    if conversation_history:
        for msg in conversation_history:
            role = "model" if msg.get("role") == "assistant" else "user"
            history.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("content", ""))]
            ))

    # 2. Configure model with manual function calling
    config = types.GenerateContentConfig(
        temperature=0.3,
        tools=AVAILABLE_TOOLS,
        system_instruction=system_prompt,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

    # 3. Create a Chat session which automatically handles thought_signatures and turns
    chat = client.aio.chats.create(
        model=settings.default_chat_model,
        history=history,
        config=config
    )
    
    tools_used = []
    in_tok = 0
    out_tok = 0
    
    # Send the initial user message
    message_to_send = user_message
    
    for i in range(max_iterations):
        log.info(f"Agent Iteration {i+1}/{max_iterations}")
        
        response = await chat.send_message(message_to_send)
        
        if response.usage_metadata:
            in_tok += response.usage_metadata.prompt_token_count
            out_tok += response.usage_metadata.candidates_token_count
            
        # Check if model wants to call tools
        if response.function_calls:
            func_response_parts = []
            
            for fc in response.function_calls:
                func_name = fc.name
                func_args = fc.args
                log.info(f"Agent calling tool: {func_name} with args: {func_args}")
                tools_used.append(func_name)
                
                # Execute tool
                if func_name in TOOL_MAP:
                    try:
                        kwargs = {}
                        if func_args:
                            for k, v in func_args.items():
                                kwargs[k] = v
                        tool_result = await TOOL_MAP[func_name](**kwargs)
                        tool_response_text = str(tool_result)
                    except Exception as e:
                        log.error(f"Tool {func_name} error: {e}")
                        tool_response_text = f"Error executing {func_name}: {e}"
                else:
                    tool_response_text = f"Tool {func_name} not found."
                
                # Build function response part
                part = types.Part.from_function_response(
                    name=func_name,
                    response={"result": tool_response_text}
                )
                if hasattr(fc, 'id') and fc.id:
                    part.function_response.id = fc.id
                    
                func_response_parts.append(part)
                
            # The next message to send is the tool responses
            message_to_send = func_response_parts
            continue
            
        # Model generated text
        final_answer = response.text
        return {
            "answer": final_answer,
            "tools_used": tools_used,
            "iterations": i + 1,
            "input_tokens": in_tok,
            "output_tokens": out_tok
        }
        
    return {
        "answer": "I'm sorry, I couldn't complete the task in the allowed number of steps.",
        "tools_used": tools_used,
        "iterations": max_iterations,
        "input_tokens": in_tok,
        "output_tokens": out_tok
    }

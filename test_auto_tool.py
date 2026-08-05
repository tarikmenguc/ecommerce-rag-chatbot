import asyncio
import os
from google.genai import types, Client

async def my_tool(query: str) -> str:
    """Returns a mocked search result."""
    return f"Result for {query}"

async def main():
    client = Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    config = types.GenerateContentConfig(
        tools=[my_tool],
        temperature=0.1,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
    )
    
    print("Sending request...")
    res = await client.aio.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Use the my_tool to search for perfume.",
        config=config
    )
    print("Response text:", res.text)
    
    # Check if we can extract used tools
    print("Function calls:", res.function_calls)
    if res.candidates:
        print("Candidates:", res.candidates[0])

if __name__ == "__main__":
    asyncio.run(main())

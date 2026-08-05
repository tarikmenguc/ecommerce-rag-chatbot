import asyncio
import os
from google.genai import types, Client

async def search_products(query: str) -> str:
    """Returns a mocked search result."""
    return f"Result for {query}"

async def main():
    client = Client(api_key=os.environ.get("GEMINI_API_KEY", "your_api_key"))
    
    config = types.GenerateContentConfig(
        tools=[search_products],
        temperature=0.1,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )
    
    chat = client.aio.chats.create(model="gemini-3.5-flash-lite", config=config)
    
    print("Sending request...")
    res = await chat.send_message("search for perfume")
    print("Response parts:", res.candidates[0].content.parts)
    
    if res.function_calls:
        print("Model requested function call.")
        fc = res.function_calls[0]
        
        # Execute tool
        result = await search_products(**fc.args)
        
        # Create function response part
        part = types.Part.from_function_response(
            name=fc.name,
            response={"result": result}
        )
        if hasattr(fc, 'id') and fc.id:
            part.function_response.id = fc.id
            
        print("Sending function response...")
        res2 = await chat.send_message(part)
        print("Final response:", res2.text)

if __name__ == "__main__":
    asyncio.run(main())

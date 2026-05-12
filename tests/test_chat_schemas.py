from pydantic import ValidationError
import pytest
from app.schemas import ChatRequest, ChatResponse

def test_chat_request():
    req=ChatRequest(message="hello deneme") 
    assert req.message == "hello deneme"
    assert req.model is None 
    assert req.system_prompt is None 
    
def test_chat_request_empty_message_fails():
    with pytest.raises(ValidationError):
        ChatRequest(message="")    

def test_chat_max_too_long_fails():
    with pytest.raises(ValidationError):
        ChatRequest(message="a" * 4001)

def test_chat_request_missing_message_fails():
    with pytest.raises(ValidationError):
        ChatRequest(model="gpt-4o-mini")

def test_chat_response_creation():
    resp = ChatResponse(
        answer="İyiyim, sen nasılsın?",
        model="gpt-4o",
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.005,
        latency_ms=150.5
    )
    
    assert resp.answer == "İyiyim, sen nasılsın?"
    assert resp.cost_usd == 0.005



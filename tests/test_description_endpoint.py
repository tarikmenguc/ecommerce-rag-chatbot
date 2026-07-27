import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)

@patch("app.routers.description.generate_ecommerce_description", new_callable=AsyncMock)
def test_generate_description_endpoint(mock_generate):
    # The decorated timed_llm_call returns the first element (the text response)
    mock_generate.return_value = "Mocked e-commerce description for a test product."

    payload = {
        "product_name": "Test Cüzdan",
        "features": "Siyah, hakiki deri"
    }

    response = client.post("/description/generate", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "ecommerce-llama3"
    assert "Mocked" in data["description"]
    
    # Assert the mock was called correctly
    mock_generate.assert_called_once()
    called_prompt = mock_generate.call_args[0][0]
    assert "Test Cüzdan" in called_prompt
    assert "Siyah, hakiki deri" in called_prompt

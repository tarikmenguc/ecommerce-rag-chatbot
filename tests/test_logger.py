"""Week 1 homework: test your hand-written logger AI-off.

Targets:
  1. LlmCall.total_cost_usd computes correctly for gpt-4o-mini.
  2. log_llm_call persists a row to llm_call_log.
  3. log_llm_call raises CostCapExceeded when daily total > cap.
"""
import pytest

from app.logger import LlmCall, CostCapExceeded


def test_llmcall_cost_math_for_gpt4o_mini():
    # 1000 input tokens @ $0.15/1M = $0.00015
    # 500 output tokens @ $0.60/1M = $0.00030
    # total = $0.00045
    call = LlmCall(
        caller="t",
        api_key="test-key",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=1.0,
    )
    assert abs(call.input_cost_usd - 0.00015) < 1e-9
    assert abs(call.output_cost_usd - 0.00030) < 1e-9
    assert abs(call.total_cost_usd - 0.00045) < 1e-9


@pytest.mark.asyncio
async def test_log_llm_call_persists_row():
    from app.logger import log_llm_call, LlmCall
    from app.models import LlmCallLog
    from unittest.mock import AsyncMock, MagicMock, patch

    call = LlmCall(
        caller="test_logger",
        api_key="test-api-key",
        model="gemini-3.5-flash",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=100.0,
    )
    
    # Mock session_scope
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0.0)))
    mock_session.add = MagicMock()
    
    # Create an async context manager mock
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.logger.session_scope", return_value=AsyncContextManagerMock()):
        await log_llm_call(call)
        
    # Assert add was called with our row
    mock_session.add.assert_called_once()
    added_row = mock_session.add.call_args[0][0]
    assert isinstance(added_row, LlmCallLog)
    assert added_row.model == "gemini-3.5-flash"
    assert added_row.api_key == "test-api-key"
    assert added_row.total_cost_usd == 0.0


@pytest.mark.asyncio
async def test_cost_cap_triggers():
    from app.logger import log_llm_call, LlmCall, CostCapExceeded
    from unittest.mock import AsyncMock, MagicMock, patch
    
    massive_call = LlmCall(
        caller="test_logger",
        api_key="expensive-key",
        model="gpt-4o",
        input_tokens=0,
        output_tokens=100_000, # $1.00 cost
        latency_ms=10.0,
    )
    
    mock_session = AsyncMock()
    # Mock the scalar() to return a high existing cost that pushes us over the cap
    # The cap is 0.50, and massive_call is 1.00. 
    # But wait, even if existing cost is 0.0, 0.0 + 1.00 > 0.50, so it will exceed.
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0.0)))
    
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    with patch("app.logger.session_scope", return_value=AsyncContextManagerMock()):
        with pytest.raises(CostCapExceeded):
            await log_llm_call(massive_call)

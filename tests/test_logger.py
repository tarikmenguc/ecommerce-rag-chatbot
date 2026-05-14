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
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=1.0,
    )
    assert abs(call.input_cost_usd - 0.00015) < 1e-9
    assert abs(call.output_cost_usd - 0.00030) < 1e-9
    assert abs(call.total_cost_usd - 0.00045) < 1e-9


@pytest.mark.skip(reason="AI-off homework")
@pytest.mark.asyncio
async def test_log_llm_call_persists_row():
    # TODO (AI-off): implement once logger.log_llm_call is real.
    raise NotImplementedError("Fill in by hand after logger is implemented.")


@pytest.mark.skip(reason="AI-off homework")
@pytest.mark.asyncio
async def test_cost_cap_triggers():
    # TODO (AI-off): seed rows above the cap, call log_llm_call,
    # assert CostCapExceeded is raised.
    raise NotImplementedError("Fill in by hand after logger is implemented.")

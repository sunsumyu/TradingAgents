"""Tests for ProgressCallbackHandler — real-time LLM call status reporting."""

import threading
from unittest.mock import MagicMock

import pytest


class TestProgressCallbackHandler:
    """Unit tests for the callback handler itself."""

    def _make_handler(self):
        from tradingagents.api_callbacks import ProgressCallbackHandler
        return ProgressCallbackHandler()

    def test_on_chat_model_start_emits_event(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"},
            messages=[{"role": "user", "content": "test"}],
            run_id="run-1",
            metadata={"langgraph_node": "Market Analyst"},
        )
        assert len(events) == 1
        assert events[0]["status"] == "in_progress"
        assert "Markets" in events[0]["message"] or "Market" in events[0]["agent"]

    def test_on_chat_model_end_emits_event(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[],
            run_id="run-1", metadata={"langgraph_node": "Bull Researcher"},
        )
        mock = MagicMock()
        mock_g = MagicMock()
        mock_g.message.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
        mock.generations = [[mock_g]]
        handler.on_llm_end(response=mock, run_id="run-1")
        assert len(events) == 2
        assert events[1]["status"] == "completed"

    def test_on_tool_start_emits_event(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_tool_start(
            serialized={"name": "get_stock_data"}, input_str="AAPL",
            run_id="run-2", metadata={"langgraph_node": "tools_market"},
        )
        assert len(events) == 1
        assert events[0]["status"] == "in_progress"

    def test_on_tool_end_is_noop(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_tool_start(serialized={"name": "get_stock_data"}, input_str="AAPL", run_id="run-2")
        handler.on_tool_end(output="data...", run_id="run-2")
        assert len(events) == 1

    def test_agent_name_from_metadata(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[],
            run_id="run-3", metadata={"langgraph_node": "Fundamentals Analyst"},
        )
        assert "Fundamentals" in events[0]["agent"]

    def test_agent_name_fallback_to_serialized(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[],
            run_id="run-4", tags=[], metadata={},
        )
        assert events[0]["agent"] == "ChatAnthropic"

    def test_no_sink_does_not_crash(self):
        handler = self._make_handler()
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[], run_id="run-5",
        )

    def test_thread_safety(self):
        handler = self._make_handler()
        events = []
        lock = threading.Lock()
        def safe_append(e):
            with lock:
                events.append(e)
        handler.set_event_sink(safe_append)

        def call_llm(i):
            handler.on_chat_model_start(
                serialized={"name": "ChatOpenAI"}, messages=[],
                run_id=f"run-{i}",
                metadata={"langgraph_node": "Bull Researcher"},
                tags=[],
            )
        threads = [threading.Thread(target=call_llm, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Dedup prevents duplicates — but no crash = success
        assert len(events) >= 1

    def test_dedup_in_progress_events(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[],
            run_id="run-a", metadata={"langgraph_node": "Market Analyst"},
        )
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[],
            run_id="run-b", metadata={"langgraph_node": "Market Analyst"},
        )
        in_progress = [e for e in events if e["status"] == "in_progress"]
        assert len(in_progress) == 1

    def test_fatal_error_sets_flag(self):
        handler = self._make_handler()
        events = []
        handler.set_event_sink(events.append)
        error_msgs = []
        handler.set_error_callback(error_msgs.append)
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[],
            run_id="run-err", metadata={"langgraph_node": "Fundamentals Analyst"},
        )
        handler.on_llm_error(error=RuntimeError("Error code: 502"), run_id="run-err")
        assert handler.has_fatal_error
        assert len(error_msgs) == 1
        assert "502" in error_msgs[0]


class TestRunnerCallbackIntegration:
    def test_handler_has_required_methods(self):
        from tradingagents.api_callbacks import ProgressCallbackHandler
        handler = ProgressCallbackHandler()
        assert hasattr(handler, "on_chat_model_start")
        assert hasattr(handler, "on_chat_model_end")
        assert hasattr(handler, "on_llm_end")
        assert hasattr(handler, "on_tool_start")

    def test_handler_emits_phase_and_agent(self):
        from tradingagents.api_callbacks import ProgressCallbackHandler
        handler = ProgressCallbackHandler()
        events = []
        handler.set_event_sink(events.append)
        handler.on_chat_model_start(
            serialized={"name": "ChatAnthropic"}, messages=[],
            run_id="run-1", metadata={"langgraph_node": "Fundamentals Analyst"},
        )
        event = events[0]
        assert "phase" in event
        assert "agent" in event
        assert "status" in event
        assert "message" in event
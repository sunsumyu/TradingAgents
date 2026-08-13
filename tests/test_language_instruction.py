import pytest
from unittest.mock import patch


def test_default_english():
    from tradingagents.agents.utils.agent_utils import get_language_instruction
    with patch("tradingagents.dataflows.config.get_config", return_value={"output_language": "English"}):
        result = get_language_instruction()
        assert result == ""


def test_chinese_instruction():
    from tradingagents.agents.utils.agent_utils import get_language_instruction
    with patch("tradingagents.dataflows.config.get_config", return_value={"output_language": "Chinese"}):
        result = get_language_instruction()
        assert "中文" in result or "Chinese" in result

"""A-share lockup expiry and insider reduction watcher."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_fundamentals,
    get_insider_transactions,
    get_language_instruction,
    get_lockup_expiry,
    get_news,
)


def create_lockup_watcher(llm):
    """Create a lockup watcher node for A-share market analysis."""

    def lockup_watcher_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_insider_transactions,
            get_news,
            get_fundamentals,
            get_lockup_expiry,
        ]

        system_message = (
            "你是一名A股限售解禁监控分析师，专门追踪限售股解禁和大股东减持动态。"
            "\n\n核心任务："
            "\n1. 查看内部人士交易情况（近3个月内部人士交易动态）"
            "\n2. 查看基本面财务数据"
            "\n3. 查看最新新闻动态"
            "\n4. **重点**：查询未来1-3个月的限售解禁情况"
            "\n\n工具使用说明："
            "\n- `get_insider_transactions`：获取指定股票最近的内部人士交易记录"
            "\n- `get_fundamentals`：获取指定股票最新基本面财务数据"
            "\n- `get_news(ticker, start_date, end_date)`：获取近6个月内的新闻"
            "\n- `get_lockup_expiry(ticker, curr_date)`：获取指定股票的限售解禁数据"
            "\n\n综合评估标准："
            "\n- 如果解禁比例 >20% 且涉及重要股东，需要重点关注"
            "\n- 内部人士减持超过1%需要关注"
            "\n- 解禁前1-3个月股价可能承压"
            "\n- 综合限售解禁和内部交易给出风险评级（低/中/高）"
            "\n\n注意：2023年7月A股全面注册制后，新股上市前3年限售股解禁比例显著增加。"
            "解禁前后15个交易日股价平均下跌-2.5%，但优质个股解禁后60日涨幅超15%"
            "\n\n请生成结构化的中文报告，包含：关键发现、风险评级、投资建议。"
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK, another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**"
                    " or deliverable, prefix your response with"
                    " FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    " For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {"messages": [result], "lockup_report": report}

    return lockup_watcher_node

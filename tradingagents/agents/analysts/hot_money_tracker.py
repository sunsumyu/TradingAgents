"""A-share hot money tracker: analyzes capital flows, volume anomalies, and major player movements."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_concept_blocks,
    get_dragon_tiger_board,
    get_fund_flow,
    get_hot_stocks,
    get_industry_comparison,
    get_insider_transactions,
    get_language_instruction,
    get_news,
    get_northbound_flow,
    get_stock_data,
)


def create_hot_money_tracker(llm):
    """Create a hot money tracker node for A-share market analysis."""

    def hot_money_tracker_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_stock_data,
            get_news,
            get_insider_transactions,
            get_hot_stocks,
            get_northbound_flow,
            get_concept_blocks,
            get_fund_flow,
            get_dragon_tiger_board,
            get_industry_comparison,
        ]

        system_message = (
            "你是A股热钱追踪器，专门分析资金流向、量价异常和主力动向。请用中文回答所有问题。"
            "\n\n### 任务："
            "\n- 分析北向资金、融资融券、龙虎榜、主力资金流向，识别游资热钱动向"
            "\n- 监控大单异动（超过10%流通股本的大单买卖），判断主力操作意图"
            "\n- 跟踪热门板块轮动，分析概念炒作持续性，提示跟风风险"
            "\n- 监控大宗交易、盘后龙虎榜、主力增减持公告，判断机构真实意图"
            "\n- 分析资金流入流出与股价背离，识别诱多诱空陷阱"
            "\n\n输出要求："
            "\n1. 使用 get_stock_data 获取K线和量价数据"
            "\n2. 使用 get_insider_transactions 获取股东增减持、高管交易"
            "\n3. 使用 get_news 获取公司公告和行业新闻"
            "\n4. 使用 get_hot_stocks 获取热股和游资席位数据"
            "\n5. 使用 get_northbound_flow 获取北向资金流向"
            "\n6. 按【资金流分析】【量价异动】【主力行为】【风险提示】四个维度组织报告"
            "\n\n分析框架："
            "\n1. 量价关系：量能放大配合价格突破，量价背离需警惕"
            "\n2. 资金流向：北向+主力+游资三方验证"
            "\n3. 主力行为：控盘程度+拉升打压时机判断"
            "\n4. 风险控制：诱多诱空识别，跟风风险提示"
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants. "
                    "Use the provided tools to progress toward answering the question. "
                    "If you are unable to fully answer, that's OK; another assistant with different tools "
                    "will help where you left off. Execute what you can to make progress. "
                    "If you or any other assistant has a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable, "
                    "prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop. "
                    "You have access to the following tools: {tool_names}.\n{system_message}\n\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
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

        return {"messages": [result], "hot_money_report": report}

    return hot_money_tracker_node

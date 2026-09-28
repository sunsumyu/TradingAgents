"""产业链模块 — 产业链平台（概念板块映射为产业链卡片）。

Data source: 东方财富 concept board data via akshare

Functions:
    get_industry_chain_categories() — 产业链分类树（化工/有色/建材等大类）
    get_industry_chain_chains()     — 产业链卡片列表（最热/最新/全部）
    get_industry_chain_overview()   — 聚合数据
"""

from __future__ import annotations
import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


# 产业链分类树（对标通达信左侧目录）
CHAIN_CATEGORIES = {
    "化工": [
        "涤纶纤维", "氟化工", "改性塑料", "功能涂料", "化学纤维",
        "胶黏剂", "聚氨酯", "煤化工", "膜材料", "碳纤维", "纤维",
    ],
    "有色": [
        "超导材料", "金属锗", "蓝宝石", "稀土", "有色金属",
    ],
    "建材": [
        "保温材料", "建筑材料",
    ],
    "农林牧渔": [
        "畜禽养殖", "生猪", "植物种植",
    ],
    "食品饮料": [
        "食品饮料",
    ],
    "轻工制造": [
        "家居生活", "造纸包装", "谷子经济",
    ],
    "家电": [
        "家电",
    ],
    "商贸": [
        "新零售",
    ],
    "汽车": [
        "Model3", "车机(智能驾驶舱)", "轮胎", "汽车变速器", "汽车车身",
    ],
    "能源": [
        "原油", "动力煤", "焦炭", "焦煤", "多晶硅", "天然气",
        "火电产量", "水电产量", "风电产量", "国内汽油", "国内柴油",
    ],
    "钢铁": [],
    "有色金属2": [],
    "建材家具": [],
    "造纸印刷": [],
    "畜牧业": [],
    "种植业": [],
    "渔业": [],
    "食品饮料2": [],
    "纺织服装": [],
    "生物医药": [],
    "交通运输": [],
    "电子电器": [],
    "金融保险": [],
    "房地产": [],
}

# 热门产业链（对标通达信"最热产业链"卡片）
HOT_CHAINS = [
    "光模块", "无人驾驶", "新基建-人工智能", "商业航天",
    "新能源汽车", "电化学储能", "半导体", "AI服务器",
]

# 最新产业链（对标通达信"最新产业链"卡片）
NEW_CHAINS = [
    "AI眼镜", "人形机器人", "商业航天", "智谱AI汽车",
    "光模块", "Soc芯片", "半导体设备", "AI传媒",
]

# 全部产业链卡片
ALL_CHAINS = [
    "半导体-芯片制造", "半导体-晶体材料", "半导体-集成电路",
    "3D成像", "3D打印", "C919", "iPhoneX", "LED",
    "LED车灯", "Model3", "NCP防护用品", "NCP医药",
    "OLED", "VR", "半导体材料", "半导体",
]


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning("akshare %s failed: %s", fn.__name__, e)
        return None


def get_industry_chain_categories() -> dict[str, Any]:
    """产业链分类树。
    
    Returns { "categories": { "化工": [...], ... }, "count": N }
    """
    return {
        "categories": CHAIN_CATEGORIES,
        "count": len(CHAIN_CATEGORIES),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_industry_chain_chains() -> dict[str, Any]:
    """产业链卡片列表。
    
    Returns { "hot": [...], "new": [...], "all": [...] }
    
    Enriched with concept board data (change_pct, etc.) from eastmoney.
    """
    import akshare as ak
    
    # Try to get concept board data for enrichment
    concept_df = _safe_call(ak.stock_board_concept_name_em)
    concept_map = {}
    if concept_df is not None and not concept_df.empty:
        for _, row in concept_df.iterrows():
            name = str(row.get("板块名称", ""))
            concept_map[name] = {
                "change_pct": float(row.get("涨跌幅", 0)) if row.get("涨跌幅") else 0,
                "total_market_cap": row.get("总市值", None),
            }
    
    def enrich(names):
        result = []
        for name in names:
            info = concept_map.get(name, {})
            result.append({
                "name": name,
                "change_pct": info.get("change_pct", 0),
                "has_data": name in concept_map,
            })
        return result
    
    return {
        "hot": enrich(HOT_CHAINS),
        "new": enrich(NEW_CHAINS),
        "all": enrich(ALL_CHAINS),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_industry_chain_overview() -> dict[str, Any]:
    """聚合产业链数据。
    
    Returns { "categories": {...}, "chains": {...} }
    """
    return {
        "categories": get_industry_chain_categories(),
        "chains": get_industry_chain_chains(),
    }

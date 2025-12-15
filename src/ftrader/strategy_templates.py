"""策略模板模块"""

from typing import Dict, List, Any, Optional


class StrategyTemplate:
    """策略模板"""
    
    def __init__(self, id: str, name: str, description: str, config_yaml: str, category: str = "default"):
        self.id = id
        self.name = name
        self.description = description
        self.config_yaml = config_yaml
        self.category = category


# 策略模板列表
TEMPLATES: List[StrategyTemplate] = []


def register_template(template: StrategyTemplate):
    """注册策略模板"""
    TEMPLATES.append(template)


def get_template(template_id: str) -> Optional[StrategyTemplate]:
    """获取策略模板"""
    for template in TEMPLATES:
        if template.id == template_id:
            return template
    return None


def get_all_templates() -> List[Dict[str, Any]]:
    """获取所有策略模板"""
    return [
        {
            'id': t.id,
            'name': t.name,
            'description': t.description,
            'category': t.category,
        }
        for t in TEMPLATES
    ]


# 注册默认模板

# 马丁格尔策略模板
martingale_template = StrategyTemplate(
    id="martingale",
    name="马丁格尔策略",
    description="马丁格尔抄底策略，价格下跌时按倍数加仓",
    category="加仓策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对，格式：基础货币/报价货币:结算货币
  side: "long"  # 交易方向：long(做多) 或 short(做空)
  leverage: 10  # 杠杆倍数

# 马丁格尔策略参数
martingale:
  initial_position: 200  # 初始仓位（USDT）
  multiplier: 2.0  # 加仓倍数
  max_additions: 5  # 最大加仓次数

# 触发条件
trigger:
  price_drop_percent: 5.0  # 价格下跌百分比阈值（触发抄底）
  start_immediately: true  # 是否立即开始（true: 启动时立即开仓，false: 等待触发条件）
  addition_cooldown: 60  # 加仓冷却时间（秒），防止频繁加仓，默认60秒

# 风险管理
risk:
  stop_loss_percent: 10.0  # 止损百分比（相对于开仓价格）
  take_profit_percent: 15.0  # 止盈百分比（相对于开仓价格）
  max_loss_percent: 20.0  # 最大亏损百分比（总资金）

# 监控设置
monitoring:
  check_interval: 5  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度（小数位数）
"""
)
register_template(martingale_template)


# DCA (定投) 策略模板
dca_template = StrategyTemplate(
    id="dca",
    name="DCA定投策略",
    description="定期定额投资策略，按固定时间间隔和金额买入",
    category="定投策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "long"  # 交易方向：long(做多)
  leverage: 1  # 杠杆倍数（定投建议使用1倍）

# DCA策略参数
dca:
  investment_amount: 100  # 每次投资金额（USDT）
  interval_minutes: 60  # 投资间隔（分钟）
  max_investments: 10  # 最大投资次数
  price_threshold_percent: 0  # 价格阈值百分比（0表示无条件买入，>0表示价格下跌超过阈值才买入）

# 触发条件
trigger:
  start_immediately: true  # 是否立即开始

# 风险管理
risk:
  stop_loss_percent: 20.0  # 止损百分比
  take_profit_percent: 30.0  # 止盈百分比
  max_loss_percent: 25.0  # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 60  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度
"""
)
register_template(dca_template)


# 网格交易策略模板
grid_template = StrategyTemplate(
    id="grid",
    name="网格交易策略",
    description="在价格区间内设置买卖网格，低买高卖赚取差价",
    category="网格策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "long"  # 交易方向
  leverage: 3  # 杠杆倍数

# 网格策略参数
grid:
  grid_count: 10  # 网格数量
  grid_spacing_percent: 2.0  # 网格间距百分比
  order_amount: 50  # 每个网格订单金额（USDT）
  upper_price: 0  # 网格上边界价格（0表示使用当前价格+10%）
  lower_price: 0  # 网格下边界价格（0表示使用当前价格-10%）

# 触发条件
trigger:
  start_immediately: true  # 是否立即开始

# 风险管理
risk:
  stop_loss_percent: 15.0  # 止损百分比
  take_profit_percent: 20.0  # 止盈百分比
  max_loss_percent: 20.0  # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 10  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度
"""
)
register_template(grid_template)


# 趋势跟踪策略模板
trend_following_template = StrategyTemplate(
    id="trend_following",
    name="趋势跟踪策略",
    description="跟踪价格趋势，在趋势确认后开仓，趋势反转时平仓",
    category="趋势策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "long"  # 交易方向
  leverage: 5  # 杠杆倍数

# 趋势跟踪策略参数
trend_following:
  position_size: 200  # 仓位大小（USDT）
  ma_period_short: 10  # 短期均线周期
  ma_period_long: 30  # 长期均线周期
  trend_confirmation_percent: 1.0  # 趋势确认百分比

# 触发条件
trigger:
  start_immediately: false  # 等待趋势确认

# 风险管理
risk:
  stop_loss_percent: 8.0  # 止损百分比
  take_profit_percent: 12.0  # 止盈百分比
  max_loss_percent: 15.0  # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 30  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度
"""
)
register_template(trend_following_template)


# 均值回归策略模板
mean_reversion_template = StrategyTemplate(
    id="mean_reversion",
    name="均值回归策略",
    description="当价格偏离均值时开仓，回归均值时平仓",
    category="回归策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "long"  # 交易方向
  leverage: 3  # 杠杆倍数

# 均值回归策略参数
mean_reversion:
  position_size: 150  # 仓位大小（USDT）
  ma_period: 20  # 均线周期
  deviation_threshold_percent: 3.0  # 偏离阈值百分比
  reversion_target_percent: 1.5  # 回归目标百分比

# 触发条件
trigger:
  start_immediately: false  # 等待偏离信号

# 风险管理
risk:
  stop_loss_percent: 10.0  # 止损百分比
  take_profit_percent: 5.0  # 止盈百分比
  max_loss_percent: 15.0  # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 15  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度
"""
)
register_template(mean_reversion_template)


# 做空马丁格尔策略模板
martingale_short_template = StrategyTemplate(
    id="martingale_short",
    name="做空马丁格尔策略",
    description="做空版本的马丁格尔策略，价格上涨时按倍数加仓",
    category="加仓策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "short"  # 交易方向：做空
  leverage: 10  # 杠杆倍数

# 马丁格尔策略参数
martingale:
  initial_position: 200  # 初始仓位（USDT）
  multiplier: 2.0  # 加仓倍数
  max_additions: 5  # 最大加仓次数

# 触发条件
trigger:
  price_drop_percent: 5.0  # 价格上涨百分比阈值（做空时价格上涨触发）
  start_immediately: true  # 是否立即开始
  addition_cooldown: 60  # 加仓冷却时间（秒），防止频繁加仓

# 风险管理
risk:
  stop_loss_percent: 10.0  # 止损百分比
  take_profit_percent: 15.0  # 止盈百分比
  max_loss_percent: 20.0  # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 5  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度
"""
)
register_template(martingale_short_template)


# 保守型马丁格尔策略模板
martingale_conservative_template = StrategyTemplate(
    id="martingale_conservative",
    name="保守型马丁格尔策略",
    description="低风险版本的马丁格尔策略，较小的加仓倍数和更严格的止损",
    category="加仓策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "long"  # 交易方向
  leverage: 5  # 杠杆倍数（较低）

# 马丁格尔策略参数
martingale:
  initial_position: 100  # 初始仓位（USDT，较小）
  multiplier: 1.5  # 加仓倍数（较小）
  max_additions: 3  # 最大加仓次数（较少）

# 触发条件
trigger:
  price_drop_percent: 3.0  # 价格下跌百分比阈值（较小）
  start_immediately: true  # 是否立即开始

# 风险管理
risk:
  stop_loss_percent: 5.0  # 止损百分比（较严格）
  take_profit_percent: 10.0  # 止盈百分比
  max_loss_percent: 10.0  # 最大亏损百分比（较严格）

# 监控设置
monitoring:
  check_interval: 5  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度
"""
)
register_template(martingale_conservative_template)


# 激进型马丁格尔策略模板
martingale_aggressive_template = StrategyTemplate(
    id="martingale_aggressive",
    name="激进型马丁格尔策略",
    description="高风险高收益版本的马丁格尔策略，较大的加仓倍数",
    category="加仓策略",
    config_yaml="""# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "long"  # 交易方向
  leverage: 20  # 杠杆倍数（较高）

# 马丁格尔策略参数
martingale:
  initial_position: 300  # 初始仓位（USDT，较大）
  multiplier: 3.0  # 加仓倍数（较大）
  max_additions: 6  # 最大加仓次数（较多）

# 触发条件
trigger:
  price_drop_percent: 7.0  # 价格下跌百分比阈值
  start_immediately: true  # 是否立即开始

# 风险管理
risk:
  stop_loss_percent: 15.0  # 止损百分比
  take_profit_percent: 20.0  # 止盈百分比
  max_loss_percent: 30.0  # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 3  # 价格检查间隔（秒，更频繁）
  price_precision: 2  # 价格精度
"""
)
register_template(martingale_aggressive_template)


# ETH 马丁格尔策略模板
martingale_eth_template = StrategyTemplate(
    id="martingale_eth",
    name="ETH马丁格尔策略",
    description="针对ETH/USDT交易对的马丁格尔策略",
    category="加仓策略",
    config_yaml="""# 交易配置
trading:
  symbol: "ETH/USDT:USDT"  # 交易对
  side: "long"  # 交易方向
  leverage: 10  # 杠杆倍数

# 马丁格尔策略参数
martingale:
  initial_position: 200  # 初始仓位（USDT）
  multiplier: 2.0  # 加仓倍数
  max_additions: 5  # 最大加仓次数

# 触发条件
trigger:
  price_drop_percent: 5.0  # 价格下跌百分比阈值
  start_immediately: true  # 是否立即开始

# 风险管理
risk:
  stop_loss_percent: 10.0  # 止损百分比
  take_profit_percent: 15.0  # 止盈百分比
  max_loss_percent: 20.0  # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 5  # 价格检查间隔（秒）
  price_precision: 2  # 价格精度
"""
)
register_template(martingale_eth_template)
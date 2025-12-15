# LLM多因子策略指南

## 概述

LLM多因子策略是基于大语言模型（LLM）和提示词工程的多因子交易策略。该策略通过收集多个技术指标和市场因子，使用LLM进行综合分析，生成交易信号。

## 核心特性

- **多因子分析**：整合多个周期的技术指标（RSI、MACD、布林带等）
- **LLM智能分析**：使用大语言模型进行市场分析和决策
- **提示词工程**：可自定义的系统提示词和用户提示词模板
- **思维链推理**：支持Chain-of-Thought（CoT）分析过程
- **灵活配置**：支持多种LLM API提供商（OpenAI、自定义端点等）

## 配置说明

### 基本配置

```yaml
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  leverage: 10             # 杠杆倍数

llm:
  # API配置
  api_provider: "openai"   # API提供商: openai, custom
  api_key: "sk-..."        # API密钥（也可通过环境变量 OPENAI_API_KEY 设置）
  api_base: ""             # 自定义API端点（可选，用于兼容OpenAI API的第三方服务）
  model: "gpt-4o-mini"     # 模型名称
  temperature: 0.3         # 温度参数（0-1，越低越确定）
  max_tokens: 500          # 最大输出token数
  call_interval: 300       # LLM调用间隔（秒），避免频繁调用
  
  # 提示词配置
  prompt:
    enable_cot: true       # 启用思维链推理
    system_prompt: ""      # 自定义系统提示词（可选）
    user_prompt_template: "" # 自定义用户提示词模板（可选）

# 多因子配置
factors:
  lookback_periods: 100   # 历史数据回看周期
  periods: [5, 10, 20, 50] # 多周期因子计算周期
  enable_volume: true      # 是否启用成交量分析
  enable_orderbook: false  # 是否启用订单簿分析（暂未实现）

# 交易参数
trading_params:
  position_size: 200.0     # 每次开仓金额（USDT）
  max_position: 1          # 最大持仓数
  confidence_threshold: 0.7 # 置信度阈值（0-1），低于此值不执行交易

# 监控配置
monitoring:
  check_interval: 60       # 策略检查间隔（秒）

# 风险管理
risk:
  stop_loss_percent: 10.0  # 止损百分比
  take_profit_percent: 15.0 # 止盈百分比
  max_loss_percent: 20.0   # 最大亏损百分比
```

### 完整配置示例

```yaml
trading:
  symbol: "BTC/USDT:USDT"
  leverage: 10

llm:
  api_provider: "openai"
  api_key: "sk-..."  # 或通过环境变量 OPENAI_API_KEY 设置
  model: "gpt-4o-mini"
  temperature: 0.3
  max_tokens: 500
  call_interval: 300
  
  prompt:
    enable_cot: true
    # 可选：自定义系统提示词
    # system_prompt: |
    #   你是一位专业的加密货币交易分析师...
    # 可选：自定义用户提示词模板
    # user_prompt_template: |
    #   请分析以下市场数据...

factors:
  lookback_periods: 100
  periods: [5, 10, 20, 50]
  enable_volume: true

trading_params:
  position_size: 200.0
  max_position: 1
  confidence_threshold: 0.7

monitoring:
  check_interval: 60

risk:
  stop_loss_percent: 10.0
  take_profit_percent: 15.0
  max_loss_percent: 20.0
```

## 环境变量配置

可以通过环境变量设置API密钥：

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."

# Linux/Mac
export OPENAI_API_KEY="sk-..."
```

## 工作原理

### 1. 多因子数据收集

策略会收集以下因子：

- **多周期技术指标**：
  - RSI（相对强弱指标）
  - MACD（移动平均收敛散度）
  - 布林带位置
  - 移动平均线（SMA、EMA）
  - ATR（平均真实波幅）

- **价格趋势**：
  - 价格动量
  - 价格趋势方向
  - 支撑位和阻力位

- **成交量分析**（可选）：
  - 平均成交量
  - 成交量趋势
  - 成交量比率

### 2. LLM分析流程

1. **数据准备**：收集并格式化多因子数据
2. **提示词构建**：根据模板构建用户提示词
3. **LLM调用**：发送请求到LLM API
4. **响应解析**：解析JSON格式的响应
5. **信号生成**：提取交易信号和置信度

### 3. 交易决策

LLM返回的JSON格式：

```json
{
    "analysis": "分析过程（如果启用CoT）",
    "signal": "buy" | "sell" | "hold",
    "confidence": 0.0-1.0,
    "reasoning": "交易理由",
    "risk_level": "low" | "medium" | "high",
    "price_target": 50000.0  // 可选
}
```

策略会根据以下条件执行交易：

- **开仓条件**：
  - `signal` 为 `buy` 或 `sell`
  - `confidence` >= `confidence_threshold`
  - 当前无持仓

- **平仓条件**：
  - `signal` 与当前持仓方向相反
  - `confidence` >= `confidence_threshold`
  - 或触发风险管理规则

## 支持的LLM API

### OpenAI API

```yaml
llm:
  api_provider: "openai"
  api_key: "sk-..."
  model: "gpt-4o-mini"  # 或 gpt-4, gpt-3.5-turbo 等
```

### 自定义API端点

支持兼容OpenAI API格式的第三方服务：

```yaml
llm:
  api_provider: "custom"
  api_key: "your-api-key"
  api_base: "https://api.example.com/v1/chat/completions"
  model: "your-model-name"
```

## 提示词工程

### 默认系统提示词

策略使用默认的系统提示词，要求LLM输出JSON格式的分析结果。你可以自定义系统提示词来：

- 调整分析风格
- 强调特定因子
- 改变风险偏好

### 自定义提示词示例

```yaml
llm:
  prompt:
    system_prompt: |
      你是一位保守的加密货币交易分析师。
      请重点关注风险控制，只有在高置信度时才建议交易。
      
      输出格式必须是JSON：
      {
        "signal": "buy|sell|hold",
        "confidence": 0.0-1.0,
        "reasoning": "理由",
        "risk_level": "low|medium|high"
      }
    
    user_prompt_template: |
      交易对: {symbol}
      当前价格: {current_price}
      
      技术指标:
      {indicators_summary}
      
      请基于以上信息，保守地给出交易建议。
```

## 性能优化

### 1. 调整LLM调用频率

```yaml
llm:
  call_interval: 600  # 增加到10分钟，减少API调用成本
```

### 2. 使用更便宜的模型

```yaml
llm:
  model: "gpt-4o-mini"  # 比 gpt-4 便宜很多
  temperature: 0.2       # 降低温度，减少token消耗
  max_tokens: 300       # 减少最大token数
```

### 3. 调整因子周期

```yaml
factors:
  periods: [10, 20]  # 减少周期数，降低计算量
```

## 监控和日志

### 查看策略日志

```bash
# 实时查看日志
tail -f logs/strategy.log | grep "LLM"
```

### 日志示例

```
2024-01-15 10:30:00 - ftrader.strategies.llm_strategy - INFO - 正在调用LLM分析市场...
2024-01-15 10:30:05 - ftrader.strategies.llm_strategy - INFO - LLM分析完成: signal=buy, confidence=0.85
2024-01-15 10:30:05 - ftrader.strategies.llm_strategy - INFO - LLM信号建议开仓: buy, 置信度: 0.85
```

## 常见问题

### Q: 如何降低API调用成本？

A: 
1. 增加 `call_interval`（减少调用频率）
2. 使用更便宜的模型（如 `gpt-4o-mini`）
3. 降低 `max_tokens`
4. 禁用 `enable_cot`（减少输出长度）

### Q: LLM响应格式错误怎么办？

A: 策略会自动尝试从响应中提取JSON。如果仍然失败，检查：
1. 系统提示词是否要求JSON格式
2. 模型是否支持JSON输出（某些模型可能需要特殊配置）
3. 查看日志中的原始响应内容

### Q: 如何提高交易信号质量？

A:
1. 提高 `confidence_threshold`（只执行高置信度信号）
2. 优化提示词，强调风险控制
3. 使用更强的模型（如 `gpt-4`）
4. 增加因子数量和数据质量

### Q: 支持哪些LLM服务？

A: 目前支持：
- OpenAI API（官方）
- 兼容OpenAI API格式的第三方服务（通过 `api_base` 配置）

### Q: 如何自定义分析逻辑？

A: 通过自定义 `system_prompt` 和 `user_prompt_template` 来调整分析逻辑和风格。

## 最佳实践

1. **从低风险开始**：设置较高的 `confidence_threshold`（如0.8）
2. **监控API成本**：定期检查API使用量
3. **测试提示词**：在实盘前充分测试提示词效果
4. **逐步优化**：根据实际表现调整参数
5. **风险管理**：始终设置止损和止盈
6. **日志监控**：定期查看策略日志，了解LLM分析过程

## 注意事项

1. **API成本**：LLM API调用会产生费用，注意控制调用频率
2. **延迟**：LLM调用有网络延迟，不适合高频交易
3. **稳定性**：LLM输出可能不稳定，建议设置较高的置信度阈值
4. **数据质量**：确保历史数据充足，因子计算准确
5. **测试环境**：建议先在测试网环境充分测试


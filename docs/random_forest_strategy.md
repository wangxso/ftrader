# 随机森林策略使用指南

## 概述

随机森林策略是一个基于机器学习的交易策略，使用网格搜索优化超参数，通过随机森林模型预测价格走势并生成交易信号。

## 特性

- **网格搜索优化**：自动优化随机森林模型的超参数
- **技术指标特征**：使用多种技术指标（SMA、EMA、RSI、MACD、布林带等）作为特征
- **时间序列交叉验证**：使用时间序列交叉验证避免未来信息泄露
- **自动重新训练**：定期重新训练模型以适应市场变化
- **置信度阈值**：只在高置信度时执行交易

## 配置示例

```yaml
trading:
  symbol: "BTC/USDT:USDT"
  leverage: 10

ml:
  # 历史数据周期
  lookback_periods: 100
  # 预测未来几个周期
  prediction_horizon: 5
  # 最少样本数才开始训练
  min_samples_to_train: 200
  # 重新训练间隔（秒），默认24小时
  retrain_interval: 86400
  # 预测置信度阈值（0-1），只有置信度高于此值才交易
  confidence_threshold: 0.6
  
  # 网格搜索配置
  grid_search:
    enable: true
    params:
      n_estimators: [50, 100, 200]
      max_depth: [5, 10, 15, null]
      min_samples_split: [2, 5, 10]
      min_samples_leaf: [1, 2, 4]

trading_params:
  # 每次开仓金额（USDT）
  position_size: 200.0
  # 最大持仓数
  max_position: 1

risk:
  stop_loss_percent: 10.0
  take_profit_percent: 15.0
  max_loss_percent: 20.0

monitoring:
  check_interval: 60  # 检查间隔（秒）
```

## 配置参数说明

### ML 参数

- **lookback_periods**: 用于计算技术指标的历史数据周期数
- **prediction_horizon**: 预测未来几个周期（分钟）的价格走势
- **min_samples_to_train**: 最少需要多少个样本才开始训练模型
- **retrain_interval**: 模型重新训练的间隔时间（秒），建议设置为24小时（86400秒）
- **confidence_threshold**: 预测置信度阈值，只有模型预测的置信度高于此值才会执行交易

### 网格搜索参数

- **enable**: 是否启用网格搜索，如果禁用则使用默认参数
- **params**: 网格搜索的超参数范围
  - **n_estimators**: 树的数量
  - **max_depth**: 树的最大深度，null 表示不限制
  - **min_samples_split**: 分裂节点所需的最小样本数
  - **min_samples_leaf**: 叶节点所需的最小样本数

### 交易参数

- **position_size**: 每次开仓使用的金额（USDT）
- **max_position**: 最大同时持仓数（当前版本固定为1）

## 技术指标

策略使用以下技术指标作为特征：

1. **简单移动平均线 (SMA)**
2. **指数移动平均线 (EMA)**
3. **相对强弱指标 (RSI)**
4. **MACD**（移动平均收敛散度）
5. **布林带位置**
6. **价格变化率**
7. **波动率**

每个指标在多个周期（5, 10, 20, 50）下计算，形成丰富的特征向量。

## 工作流程

1. **数据收集**：收集历史价格数据
2. **特征工程**：计算技术指标，创建特征向量
3. **标签生成**：根据未来价格走势生成标签（上涨/下跌）
4. **模型训练**：
   - 如果启用网格搜索，使用时间序列交叉验证优化超参数
   - 否则使用默认参数训练
5. **预测**：使用训练好的模型预测价格方向
6. **交易决策**：
   - 如果预测置信度高于阈值，执行交易
   - 如果预测方向与持仓相反，考虑平仓
7. **定期重训练**：按照配置的间隔重新训练模型

## 注意事项

1. **数据要求**：策略需要至少 `min_samples_to_train` 个历史数据点才能开始训练
2. **训练时间**：网格搜索可能需要较长时间，建议在非交易时间进行
3. **过拟合风险**：虽然使用了时间序列交叉验证，但仍需注意过拟合
4. **市场适应性**：定期重新训练模型以适应市场变化
5. **置信度阈值**：设置合适的置信度阈值，避免低质量交易信号

## 性能优化建议

1. **减少网格搜索参数范围**：如果训练时间过长，可以减少参数组合
2. **调整重训练间隔**：根据市场波动性调整重训练频率
3. **特征选择**：可以尝试添加或移除某些技术指标
4. **样本数量**：增加 `min_samples_to_train` 可以提高模型稳定性，但需要更多历史数据

## 示例配置（快速开始）

```yaml
trading:
  symbol: "BTC/USDT:USDT"
  leverage: 10

ml:
  lookback_periods: 100
  prediction_horizon: 5
  min_samples_to_train: 200
  retrain_interval: 86400
  confidence_threshold: 0.65
  grid_search:
    enable: true
    params:
      n_estimators: [100, 200]
      max_depth: [10, 15]
      min_samples_split: [2, 5]
      min_samples_leaf: [1, 2]

trading_params:
  position_size: 200.0
  max_position: 1

risk:
  stop_loss_percent: 10.0
  take_profit_percent: 15.0
  max_loss_percent: 20.0

monitoring:
  check_interval: 60
```

## 故障排除

### 模型训练失败

- 检查是否有足够的历史数据
- 检查技术指标计算是否正常
- 查看日志中的错误信息

### 预测置信度始终很低

- 降低 `confidence_threshold`（不推荐）
- 增加训练样本数量
- 调整网格搜索参数范围
- 检查市场是否处于异常状态

### 交易频率过低

- 降低 `confidence_threshold`
- 检查是否有足够的历史数据
- 确认模型训练是否成功


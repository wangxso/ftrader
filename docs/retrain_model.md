# 模型重新训练指南

## 概述

随机森林策略支持自动和手动重新训练模型，以适应市场变化并提高预测准确性。

## 自动重新训练

### 工作原理

策略在运行过程中会自动检查是否需要重新训练：

1. **时间间隔检查**：每次执行 `run_once()` 时，检查距离上次训练的时间
2. **触发条件**：如果时间间隔 >= `retrain_interval`，自动触发重新训练
3. **数据更新**：获取最新的历史价格数据
4. **模型训练**：使用新数据重新训练模型
5. **更新模型**：替换旧的模型和标准化器

### 配置自动重新训练

在策略配置中设置 `retrain_interval`（单位：秒）：

```yaml
ml:
  # 重新训练间隔（秒）
  # 86400 = 24小时
  # 43200 = 12小时
  # 3600 = 1小时
  retrain_interval: 86400  # 默认24小时
```

### 推荐设置

- **高频交易**：1-6小时（3600-21600秒）
- **日内交易**：12-24小时（43200-86400秒）
- **中长期交易**：24-48小时（86400-172800秒）

## 手动触发重新训练

### 方法1：通过API端点（推荐）

使用 POST 请求手动触发重新训练：

```bash
# 正常重新训练（会检查时间间隔）
curl -X POST "http://localhost:8000/api/strategies/{strategy_id}/retrain"

# 强制重新训练（忽略时间间隔）
curl -X POST "http://localhost:8000/api/strategies/{strategy_id}/retrain?force=true"
```

**API 端点**：`POST /api/strategies/{strategy_id}/retrain`

**参数**：
- `force` (可选, boolean): 是否强制重新训练，忽略时间间隔限制。默认为 `false`

**响应示例**：
```json
{
  "message": "模型重新训练成功",
  "last_retrain_time": "2024-01-15T10:30:00",
  "training_samples": 500
}
```

**错误响应**：
```json
{
  "detail": "距离上次训练时间过短，还需等待 3600 秒"
}
```

### 方法2：通过Web界面

在策略详情页面添加"重新训练"按钮（需要前端实现）。

### 方法3：重启策略

停止并重新启动策略，会触发初始模型训练：

1. 在Web界面停止策略
2. 等待几秒
3. 重新启动策略

### 方法3：修改配置

修改策略配置中的 `retrain_interval` 为一个很小的值（如60秒），等待自动触发后，再改回原来的值。

## 重新训练过程

### 步骤1：数据收集

```python
# 获取历史价格数据
prices = await self.get_price_data(
    self.lookback_periods + self.min_samples_to_train
)
```

### 步骤2：特征工程

```python
# 为每个历史时间点创建特征
X = []
y = []

for i in range(min_samples_to_train, len(prices) - prediction_horizon):
    features = self.create_features(prices[:i+1])
    X.append(features)
    
    # 创建标签（未来价格走势）
    future_prices = prices[i:i+prediction_horizon+1]
    label = 1 if future_prices[-1] > future_prices[0] else 0
    y.append(label)
```

### 步骤3：模型训练

如果启用网格搜索：
- 使用时间序列交叉验证
- 搜索最佳超参数
- 训练最优模型

如果禁用网格搜索：
- 使用默认参数
- 直接训练模型

### 步骤4：模型评估

```python
# 计算训练集准确率
accuracy = accuracy_score(y, y_pred)
logger.info(f"模型训练完成，训练集准确率: {accuracy:.4f}")
```

## 重新训练日志

重新训练时会输出以下日志：

```
2024-01-15 10:30:00 - ftrader.strategies.random_forest - INFO - ============================================================
2024-01-15 10:30:00 - ftrader.strategies.random_forest - INFO - 开始重新训练模型...
2024-01-15 10:30:00 - ftrader.strategies.random_forest - INFO - 策略ID: 1, 交易对: BTC/USDT:USDT
2024-01-15 10:30:00 - ftrader.strategies.random_forest - INFO - 上次训练时间: 2024-01-14T10:30:00
2024-01-15 10:30:00 - ftrader.strategies.random_forest - INFO - ============================================================
2024-01-15 10:30:01 - ftrader.strategies.random_forest - INFO - 正在获取历史价格数据（需要至少 200 个样本）...
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 已获取 500 个价格数据点
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 价格历史已更新，共 500 个数据点
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 开始训练模型...
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 开始构建训练数据集...
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 价格历史数据点: 500
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 最小训练样本数: 200
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 预测周期: 5
2024-01-15 10:30:02 - ftrader.strategies.random_forest - INFO - 正在创建特征和标签...
2024-01-15 10:30:03 - ftrader.strategies.random_forest - INFO - 数据集构建完成: 特征数 295, 标签数 295
2024-01-15 10:30:03 - ftrader.strategies.random_forest - INFO - 特征维度: 32
2024-01-15 10:30:03 - ftrader.strategies.random_forest - INFO - 标签分布: 上涨=150, 下跌=145
2024-01-15 10:30:03 - ftrader.strategies.random_forest - INFO - 开始训练随机森林模型...
2024-01-15 10:30:03 - ftrader.strategies.random_forest - INFO - 开始网格搜索优化超参数...
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 最佳参数: {'n_estimators': 200, 'max_depth': 10, ...}
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 最佳交叉验证得分: 0.6523
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 模型训练完成，训练集准确率: 0.6789
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 初始模型训练完成
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 训练完成时间: 2024-01-15T10:30:15
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - ============================================================
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 模型重新训练完成
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 训练样本数: 500
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - 下次训练时间: 2024-01-16T10:30:15
2024-01-15 10:30:15 - ftrader.strategies.random_forest - INFO - ============================================================
```

**注意**：如果日志没有显示，请检查：
1. 日志文件是否存在：`logs/strategy.log`
2. 日志级别是否设置为 INFO 或更低（DEBUG）
3. 查看控制台输出（如果通过 `start_web.py` 启动）

## 何时需要重新训练

### 1. 定期重新训练（推荐）

- **市场环境变化**：市场从牛市转为熊市，或反之
- **波动性变化**：市场波动性显著增加或减少
- **周期性变化**：适应市场的周期性模式

### 2. 性能下降时

如果观察到以下情况，应该考虑重新训练：

- **预测准确率下降**：模型预测的准确率明显降低
- **交易信号质量下降**：置信度持续低于阈值
- **交易结果变差**：连续亏损或胜率下降

### 3. 数据积累后

- **新数据积累**：收集到足够的新数据（建议至少200个新样本）
- **特征分布变化**：技术指标的分布发生显著变化

## 优化重新训练

### 1. 调整训练样本数量

```yaml
ml:
  min_samples_to_train: 300  # 增加样本数提高稳定性
```

### 2. 调整网格搜索参数

减少参数组合可以加快训练速度：

```yaml
ml:
  grid_search:
    enable: true
    params:
      n_estimators: [100, 200]  # 减少选项
      max_depth: [10, 15]        # 减少选项
```

### 3. 禁用网格搜索（快速训练）

```yaml
ml:
  grid_search:
    enable: false  # 使用默认参数，训练更快
```

## 监控重新训练

### 查看日志

系统会自动将日志输出到控制台和日志文件。日志文件位置：`logs/strategy.log`

#### 方法1：查看日志文件

```bash
# 实时查看策略日志（Windows PowerShell）
Get-Content logs/strategy.log -Wait -Tail 50

# 实时查看策略日志（Linux/Mac）
tail -f logs/strategy.log

# 过滤重新训练相关日志
tail -f logs/strategy.log | grep "重新训练"
```

#### 方法2：查看控制台输出

如果通过 `start_web.py` 启动服务，训练日志会直接输出到控制台。

#### 方法3：通过日志级别控制

可以通过环境变量设置日志级别：

```bash
# Windows PowerShell
$env:LOG_LEVEL="INFO"  # 或 DEBUG, WARNING, ERROR
python start_web.py

# Linux/Mac
export LOG_LEVEL=INFO
python start_web.py
```

### 检查模型性能

重新训练后，观察以下指标：

1. **训练集准确率**：应该保持在合理范围（0.55-0.70）
2. **预测置信度**：重新训练后置信度应该有所提升
3. **交易表现**：观察重新训练后的交易结果

## 常见问题

### Q: 重新训练需要多长时间？

A: 取决于：
- 样本数量
- 是否启用网格搜索
- 网格搜索参数范围
- 通常需要几分钟到十几分钟

### Q: 重新训练会影响正在进行的交易吗？

A: 不会。重新训练是异步进行的，不会中断交易逻辑。训练完成后会无缝替换模型。

### Q: 如何知道模型已经重新训练？

A: 查看日志中的 "模型重新训练完成" 消息，或检查 `last_retrain_time` 字段。

### Q: 可以强制立即重新训练吗？

A: 可以！使用 API 端点并设置 `force=true` 参数：
```bash
curl -X POST "http://localhost:8000/api/strategies/{strategy_id}/retrain?force=true"
```

### Q: 手动重新训练会影响自动重新训练吗？

A: 不会。手动重新训练会更新 `last_retrain_time`，自动重新训练会基于新的时间重新计算。

## 最佳实践

1. **设置合理的重训练间隔**：不要过于频繁（浪费资源），也不要过于稀疏（模型过时）
2. **监控模型性能**：定期检查训练准确率和预测置信度
3. **保留训练日志**：记录每次重新训练的参数和性能
4. **在非交易时间训练**：如果可能，安排在市场休市时重新训练
5. **逐步调整**：根据实际效果逐步调整重训练间隔和参数


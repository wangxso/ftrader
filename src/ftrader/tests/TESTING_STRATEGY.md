# 策略测试指南

本文档说明如何测试策略是否正确运行，特别是马丁格尔抄底策略。

## 测试方法

### 1. 单元测试

运行单元测试来验证策略的核心逻辑：

```bash
# 运行所有测试
pytest

# 运行马丁格尔策略测试
pytest src/ftrader/tests/test_martingale_strategy.py -v

# 运行特定测试类
pytest src/ftrader/tests/test_martingale_strategy.py::TestMartingaleStrategy -v

# 运行特定测试方法
pytest src/ftrader/tests/test_martingale_strategy.py::TestMartingaleStrategy::test_calculate_position_size -v
```

### 2. 测试内容

测试文件 `test_martingale_strategy.py` 包含以下测试：

#### 核心逻辑测试

1. **仓位计算测试** (`test_calculate_position_size`)
   - 验证初始仓位大小
   - 验证加仓倍数计算（2倍递增）

2. **触发条件测试** (`test_check_trigger_condition_long` / `test_check_trigger_condition_short`)
   - 验证价格下跌百分比计算
   - 验证做多/做空时的触发条件

3. **加仓条件测试** (`test_should_add_position_checks`)
   - 验证最大加仓次数限制
   - 验证加仓冷却时间
   - 验证价格变化阈值

#### 完整流程测试

4. **价格下跌触发加仓** (`test_price_drop_triggers_addition`)
   - 模拟价格下跌5%
   - 验证是否触发加仓
   - 验证加仓金额是否正确（400 USDT = 200 * 2^1）

5. **多次加仓倍数验证** (`test_multiple_additions_with_correct_multiplier`)
   - 第1次加仓：400 USDT (200 * 2^1)
   - 第2次加仓：800 USDT (200 * 2^2)
   - 第3次加仓：1600 USDT (200 * 2^3)

6. **下跌百分比计算** (`test_price_drop_percent_calculation`)
   - 验证不同价格下跌百分比的触发情况
   - 5%下跌应该触发
   - 4%下跌不应该触发

7. **边界条件测试**
   - 小幅下跌不触发 (`test_strategy_does_not_add_on_small_drops`)
   - 最大加仓次数限制 (`test_strategy_respects_max_additions`)

#### 集成测试

8. **完整策略流程** (`test_complete_martingale_flow`)
   - 使用模拟交易所和K线数据
   - 验证完整的策略执行流程
   - 验证交易记录和加仓逻辑

## 如何验证策略正确运行

### 方法1：查看日志输出

启动策略后，观察日志输出：

```python
# 策略启动时会打印配置信息
启动马丁格尔策略
交易对: BTC/USDT:USDT
方向: long
杠杆: 10x
初始仓位: 200 USDT
加仓倍数: 2.0x
最大加仓次数: 5
触发阈值: 5.0%
```

当价格下跌触发加仓时，会看到：

```
触发加仓条件 (第1次加仓): 当前价格 47500.00, 参考价格 50000.00, 加仓大小 400.00 USDT
开仓成功: long 400.00 USDT @ 47500.00
```

### 方法2：检查数据库记录

策略运行后，检查数据库中的交易记录：

```python
# 查看交易记录
from ftrader.database import SessionLocal
from ftrader.models.trade import Trade

db = SessionLocal()
trades = db.query(Trade).filter(Trade.strategy_id == strategy_id).all()

for trade in trades:
    print(f"交易类型: {trade.trade_type}, 方向: {trade.side}, "
          f"价格: {trade.price}, 数量: {trade.amount}")
```

### 方法3：使用回测功能

使用回测功能验证策略逻辑：

```python
from ftrader.backtester import Backtester
from ftrader.strategies.martingale import MartingaleStrategy

# 准备K线数据（价格下跌场景）
ohlcv_data = [
    [timestamp1, 50000, 50100, 49900, 50000, 1000],  # 初始价格
    [timestamp2, 50000, 50100, 49900, 50000, 1000],
    [timestamp3, 49000, 49100, 48900, 49000, 1000],  # 下跌2%
    [timestamp4, 48000, 48100, 47900, 48000, 1000],  # 下跌4%
    [timestamp5, 47500, 47600, 47400, 47500, 1000],  # 下跌5%，应该触发加仓
    # ... 更多数据
]

config = {
    'trading': {'symbol': 'BTC/USDT:USDT', 'side': 'long', 'leverage': 10},
    'martingale': {'initial_position': 200, 'multiplier': 2.0, 'max_additions': 5},
    'trigger': {'price_drop_percent': 5.0, 'start_immediately': True},
    # ...
}

backtester = Backtester(MartingaleStrategy, config, ohlcv_data, 10000.0)
results = backtester.run()

# 检查结果
print(f"总交易次数: {results['total_trades']}")
print(f"加仓次数: {len([t for t in results['trades'] if t['trade_type'] == 'add'])}")
```

### 方法4：手动验证关键逻辑

#### 验证1：价格下跌百分比计算

```python
# 参考价格（最高价）
reference_price = 50000.0

# 当前价格
current_price = 47500.0

# 计算下跌百分比
drop_percent = ((reference_price - current_price) / reference_price) * 100
# 结果应该是 5.0%

# 如果配置的触发阈值是 5%，应该触发加仓
triggered = drop_percent >= 5.0  # True
```

#### 验证2：加仓倍数计算

```python
initial_position = 200.0
multiplier = 2.0

# 第0次（初始仓位）
size_0 = initial_position  # 200 USDT

# 第1次加仓
size_1 = initial_position * (multiplier ** 1)  # 400 USDT

# 第2次加仓
size_2 = initial_position * (multiplier ** 2)  # 800 USDT

# 第3次加仓
size_3 = initial_position * (multiplier ** 3)  # 1600 USDT
```

#### 验证3：触发条件

```python
# 做多策略：价格从最高点下跌超过阈值
def check_trigger(current_price, highest_price, threshold_percent):
    if highest_price == 0:
        return False
    drop = (highest_price - current_price) / highest_price
    return drop >= (threshold_percent / 100.0)

# 测试
highest_price = 50000.0
threshold = 5.0

# 下跌5%，应该触发
assert check_trigger(47500.0, highest_price, threshold) == True

# 下跌4%，不应该触发
assert check_trigger(48000.0, highest_price, threshold) == False
```

## 测试场景示例

### 场景1：正常下跌触发加仓

1. 初始价格：50000 USDT
2. 开仓：200 USDT @ 50000
3. 价格下跌到 47500（下跌5%）
4. **预期**：触发第1次加仓，加仓金额 400 USDT
5. 价格继续下跌到 45125（从47500下跌5%）
6. **预期**：触发第2次加仓，加仓金额 800 USDT

### 场景2：小幅下跌不触发

1. 初始价格：50000 USDT
2. 开仓：200 USDT @ 50000
3. 价格下跌到 49000（下跌2%）
4. **预期**：不触发加仓（阈值是5%）

### 场景3：达到最大加仓次数

1. 配置最大加仓次数：3次
2. 已加仓3次
3. 价格继续下跌5%
4. **预期**：不再触发加仓（已达到最大次数）

## 常见问题

### Q: 如何确认策略真的在运行？

A: 检查以下几点：
1. 策略状态为 `RUNNING`
2. 日志中有策略执行记录
3. 数据库中有交易记录
4. 账户余额有变化

### Q: 如何确认加仓倍数正确？

A: 查看交易记录中的 `amount` 字段：
- 初始开仓：200 USDT
- 第1次加仓：400 USDT (200 * 2)
- 第2次加仓：800 USDT (200 * 4)
- 第3次加仓：1600 USDT (200 * 8)

### Q: 如何确认下跌百分比计算正确？

A: 查看日志中的价格信息：
```
触发加仓条件: 当前价格 47500.00, 参考价格 50000.00
```

计算：(50000 - 47500) / 50000 * 100 = 5.0%

### Q: 测试时如何模拟价格下跌？

A: 有几种方法：
1. 使用回测功能，提供模拟K线数据
2. 使用测试网，观察真实市场波动
3. 修改交易所接口，返回模拟价格（仅用于测试）

## 运行测试示例

```bash
# 运行所有测试
pytest -v

# 运行特定测试并显示详细输出
pytest src/ftrader/tests/test_martingale_strategy.py::TestMartingaleStrategy::test_price_drop_triggers_addition -v -s

# 运行集成测试
pytest src/ftrader/tests/test_martingale_strategy.py::TestMartingaleStrategyIntegration -v

# 生成测试覆盖率报告
pytest --cov=src/ftrader/strategies --cov-report=html
```


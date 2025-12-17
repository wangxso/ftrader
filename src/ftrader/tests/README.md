# 测试说明

## 运行测试

### 安装测试依赖

首先确保已安装测试所需的依赖：

```bash
# 使用 uv (推荐)
uv sync --dev

# 或使用 pip
pip install pytest pytest-asyncio httpx
```

### 运行所有测试

```bash
pytest
```

### 运行特定测试文件

```bash
pytest src/ftrader/tests/test_account_api.py
```

### 运行特定测试类

```bash
pytest src/ftrader/tests/test_account_api.py::TestGetBalance
```

### 运行特定测试方法

```bash
pytest src/ftrader/tests/test_account_api.py::TestGetBalance::test_get_balance_with_existing_exchange
```

### 查看详细输出

```bash
pytest -v
```

### 查看覆盖率

```bash
# 需要先安装 pytest-cov
pip install pytest-cov
# 或使用 uv
uv sync --dev

# 运行覆盖率测试
pytest --cov=src/ftrader --cov-report=html

# 查看覆盖率报告（会在 htmlcov/index.html 生成）
```

## 测试结构

- `test_account_api.py`: 账户API接口的单元测试
  - `TestGetBalance`: 测试获取余额接口的各种场景
  - `TestGetBalanceIntegration`: 集成测试，使用 FastAPI TestClient 测试完整请求

- `test_strategy_manager.py`: 策略管理器单元测试（**新增**）
  - `TestStrategyManagerStopStrategy`: 测试停止策略功能（自动平仓、保存运行记录）
  - `TestStrategyManagerStartStrategy`: 测试启动策略功能（清理旧持仓、状态重置）
  - `TestStrategyManagerTradeCallback`: 测试交易回调功能（记录关联、统计更新）
  - `TestMartingaleStrategyStop`: 测试马丁格尔策略停止功能
  - `TestStrategyManagerEdgeCases`: 测试边界情况和错误处理

## 测试覆盖的场景

### 账户API测试 (test_account_api.py)
1. ✅ 当策略管理器中有交易所实例时获取余额
2. ✅ 当策略管理器中没有交易所实例时创建新的交易所
3. ✅ 使用测试网模式获取余额
4. ✅ 当没有API密钥时抛出异常
5. ✅ 当交易所获取余额失败时返回默认值
6. ✅ 不同的余额值测试
7. ✅ 完整的HTTP端点集成测试

### 策略管理器测试 (test_strategy_manager.py) - **新增**
1. ✅ 停止策略时自动平仓
2. ✅ 停止策略时保存运行记录（包括交易统计）
3. ✅ 停止策略时无持仓的情况
4. ✅ 停止策略时不平仓的情况
5. ✅ 启动策略时清理旧持仓
6. ✅ 启动策略时状态重置
7. ✅ 交易记录关联到运行记录
8. ✅ 交易统计实时更新
9. ✅ 边界情况和错误处理
10. ✅ 策略停止时的各种场景


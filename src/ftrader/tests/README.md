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
pytest --cov=src/ftrader/api --cov-report=html
```

## 测试结构

- `test_account_api.py`: 账户API接口的单元测试
  - `TestGetBalance`: 测试获取余额接口的各种场景
  - `TestGetBalanceIntegration`: 集成测试，使用 FastAPI TestClient 测试完整请求

## 测试覆盖的场景

1. ✅ 当策略管理器中有交易所实例时获取余额
2. ✅ 当策略管理器中没有交易所实例时创建新的交易所
3. ✅ 使用测试网模式获取余额
4. ✅ 当没有API密钥时抛出异常
5. ✅ 当交易所获取余额失败时返回默认值
6. ✅ 不同的余额值测试
7. ✅ 完整的HTTP端点集成测试


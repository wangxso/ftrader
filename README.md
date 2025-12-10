# 币安马丁格尔交易框架

基于 ccxt 实现的币安合约交易框架，支持马丁格尔抄底策略，支持开多/开空、杠杆交易。

## 功能特性

- ✅ 支持币安合约交易（USDT-M 和 COIN-M）
- ✅ 马丁格尔抄底策略
- ✅ 支持开多/开空
- ✅ 支持杠杆交易
- ✅ 止损止盈机制
- ✅ 最大亏损限制
- ✅ 可配置策略参数

## 项目结构

```
ftrader/
├── pyproject.toml          # 项目配置
├── config.yaml             # 策略配置文件
├── .env                    # 环境变量（需要创建）
├── README.md               # 项目说明
└── src/
    └── ftrader/
        ├── __init__.py
        ├── config.py       # 配置管理
        ├── exchange.py     # 交易所封装
        ├── risk_manager.py # 风险管理
        ├── strategy.py     # 马丁格尔策略
        └── main.py         # 主程序入口
```

## 安装

### 1. 安装依赖

**必须先安装依赖才能运行！**

使用 pip3 安装依赖：

```bash
# 安装项目依赖（包括ccxt, pyyaml, python-dotenv）
pip3 install -e .

# 或者只安装依赖包（不安装项目本身）
pip3 install ccxt pyyaml python-dotenv
```

如果遇到权限问题，可以使用 `--user` 参数：

```bash
pip3 install --user -e .
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的币安 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

**实盘配置：**
```
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
```

**测试网配置（推荐）：**
```
# 测试网需要专用的API密钥，可在 https://testnet.binancefuture.com/ 申请
# 如果设置了测试网专用密钥，使用 --testnet 时会优先使用测试网密钥
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_SECRET_KEY=your_testnet_secret_key

# 如果没有设置测试网专用密钥，会尝试使用实盘密钥（不推荐）
# 注意：实盘API密钥在测试网上可能无法使用，会提示 "Invalid Api-Key ID"
```

**重要提示：**
- 测试网和实盘使用不同的API密钥系统
- 测试网API密钥申请地址：https://testnet.binancefuture.com/
- 实盘API密钥无法在测试网使用，必须申请测试网专用密钥

### 3. 配置策略参数

编辑 `config.yaml` 文件，设置你的策略参数：

```yaml
# 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # 交易对
  side: "long"              # long(做多) 或 short(做空)
  leverage: 10              # 杠杆倍数

# 马丁格尔策略参数
martingale:
  initial_position: 100     # 初始仓位（USDT）
  multiplier: 2.0           # 加仓倍数
  max_additions: 5          # 最大加仓次数

# 触发条件
trigger:
  price_drop_percent: 5.0   # 价格下跌百分比阈值

# 风险管理
risk:
  stop_loss_percent: 10.0   # 止损百分比
  take_profit_percent: 15.0 # 止盈百分比
  max_loss_percent: 20.0    # 最大亏损百分比

# 监控设置
monitoring:
  check_interval: 5         # 价格检查间隔（秒）
  price_precision: 2        # 价格精度
```

## 使用方法

### 运行策略

有两种运行方式：

**方式1：使用便捷脚本（推荐）**

```bash
# 基本运行
python3 run.py

# 指定配置文件
python3 run.py --config my_config.yaml

# 使用测试网
python3 run.py --testnet

# 设置日志级别
python3 run.py --log-level DEBUG
```

**方式2：安装包后运行**

```bash
# 先安装包（可编辑模式）
pip3 install -e .

# 然后运行
python3 -m ftrader.main --testnet
```

**方式3：直接设置PYTHONPATH运行**

```bash
# 设置PYTHONPATH并运行
PYTHONPATH=src python3 -m ftrader.main --testnet
```

## 策略说明

### 马丁格尔策略

马丁格尔策略是一种加仓策略，当价格下跌时按倍数增加仓位：

1. **初始开仓**：当价格从最高点（做多）或最低点（做空）变化达到触发阈值时，进行初始开仓
2. **加仓机制**：每次加仓的金额 = 初始仓位 × (倍数 ^ 加仓次数)
   - 第1次加仓：初始仓位 × 2
   - 第2次加仓：初始仓位 × 4
   - 第3次加仓：初始仓位 × 8
   - ...
3. **触发条件**：每次加仓后，等待价格再次变化达到阈值时触发下一次加仓

### 风险管理

- **止损**：当价格变化超过止损百分比时，自动平仓
- **止盈**：当价格变化达到止盈百分比时，自动平仓
- **最大亏损**：当总亏损超过最大亏损百分比时，停止策略

## 注意事项

⚠️ **风险提示**：

1. 马丁格尔策略存在高风险，可能导致大幅亏损
2. 请务必在测试网充分测试后再使用实盘
3. 建议设置合理的止损和最大亏损限制
4. 杠杆交易会放大风险，请谨慎使用
5. 本框架仅供学习参考，使用需自行承担风险

## 开发

### 项目依赖

- Python 3.9+
- ccxt >= 4.0.0
- pyyaml >= 6.0
- python-dotenv >= 1.0.0

## 许可证

MIT


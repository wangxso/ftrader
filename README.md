# FTrader

> A professional cryptocurrency trading framework for Binance Futures with multi-strategy support and web-based management interface.

> 专业的币安合约交易框架，支持多策略管理和基于 Web 的管理界面。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)

## 📋 Table of Contents / 目录

- [Features / 功能特性](#features--功能特性)
- [Quick Start / 快速开始](#quick-start--快速开始)
- [Installation / 安装](#installation--安装)
- [Configuration / 配置](#configuration--配置)
- [Usage / 使用方法](#usage--使用方法)
- [Strategy Templates / 策略模板](#strategy-templates--策略模板)
- [Web Interface / Web 界面](#web-interface--web-界面)
- [Project Structure / 项目结构](#project-structure--项目结构)
- [Requirements / 依赖要求](#requirements--依赖要求)
- [Disclaimer / 免责声明](#disclaimer--免责声明)
- [License / 许可证](#license--许可证)

## Features / 功能特性

### Core Features / 核心功能

- ✅ **Multi-Strategy Support** / **多策略支持**: Run multiple trading strategies simultaneously
- ✅ **Binance Futures Trading** / **币安合约交易**: Support for USDT-M and COIN-M futures
- ✅ **Long/Short Trading** / **多空交易**: Support both long and short positions
- ✅ **Leverage Trading** / **杠杆交易**: Configurable leverage up to 125x
- ✅ **Risk Management** / **风险管理**: Built-in stop-loss, take-profit, and max-loss protection
- ✅ **Strategy Templates** / **策略模板**: Pre-built templates for common trading strategies

### Web Interface Features / Web 界面功能

- ✅ **Real-time Monitoring** / **实时监控**: WebSocket-based real-time strategy status and account updates
- ✅ **Visual Dashboard** / **可视化仪表板**: Interactive charts for P&L, price trends, and trading history
- ✅ **Strategy Management** / **策略管理**: Create, edit, start, and stop strategies via web UI
- ✅ **Data Persistence** / **数据持久化**: SQLite database for strategies, trades, and account snapshots
- ✅ **RESTful API** / **RESTful API**: Complete API documentation with Swagger UI

## Quick Start / 快速开始

### Prerequisites / 前置要求

- Python 3.9 or higher
- Node.js 16+ (for web interface)
- Binance API keys (testnet recommended for testing)

### 1. Clone the repository / 克隆仓库

```bash
git clone https://github.com/yourusername/ftrader.git
cd ftrader
```

### 2. Install dependencies / 安装依赖

**Backend / 后端:**

```bash
pip install -e .
```

**Frontend / 前端 (for web interface):**

```bash
cd frontend
npm install
cd ..
```

### 3. Configure environment / 配置环境

Copy `.env.example` to `.env` and fill in your Binance API credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Production / 实盘
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here

# Testnet (Recommended for testing) / 测试网（推荐用于测试）
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_SECRET_KEY=your_testnet_secret_key
```

> **Note / 注意**: Testnet API keys must be obtained separately from [Binance Testnet](https://testnet.binancefuture.com/). Production API keys cannot be used on testnet.

### 4. Run / 运行

**Command Line / 命令行模式:**

```bash
# Run with testnet / 使用测试网运行
python run.py --testnet

# Run with custom config / 使用自定义配置运行
python run.py --config my_config.yaml --testnet
```

**Web Interface / Web 界面模式:**

```bash
# Start backend / 启动后端
python -m uvicorn ftrader.web_server:app --host 0.0.0.0 --port 8000 --reload

# Start frontend (in another terminal) / 启动前端（在另一个终端）
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

## Installation / 安装

### Backend Installation / 后端安装

```bash
# Install in development mode / 开发模式安装
pip install -e .

# Or install dependencies only / 或仅安装依赖
pip install ccxt pyyaml python-dotenv fastapi uvicorn sqlalchemy websockets pydantic
```

### Frontend Installation / 前端安装

```bash
cd frontend
npm install
```

## Configuration / 配置

### Environment Variables / 环境变量

Create a `.env` file in the project root:

```env
# Binance API Credentials / 币安 API 凭证
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key

# Testnet Credentials (Optional) / 测试网凭证（可选）
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_SECRET_KEY=your_testnet_secret_key
```

### Strategy Configuration / 策略配置

Strategies are configured using YAML files. Example `config.yaml`:

```yaml
# Trading Configuration / 交易配置
trading:
  symbol: "BTC/USDT:USDT"  # Trading pair / 交易对
  side: "long"              # long(做多) or short(做空)
  leverage: 10              # Leverage multiplier / 杠杆倍数

# Martingale Strategy Parameters / 马丁格尔策略参数
martingale:
  initial_position: 200     # Initial position size (USDT) / 初始仓位（USDT）
  multiplier: 2.0           # Position multiplier / 加仓倍数
  max_additions: 5          # Maximum addition times / 最大加仓次数

# Trigger Conditions / 触发条件
trigger:
  price_drop_percent: 5.0   # Price drop threshold (%) / 价格下跌阈值（%）
  start_immediately: true   # Start immediately / 是否立即开始

# Risk Management / 风险管理
risk:
  stop_loss_percent: 10.0   # Stop loss (%) / 止损百分比
  take_profit_percent: 15.0 # Take profit (%) / 止盈百分比
  max_loss_percent: 20.0    # Max loss limit (%) / 最大亏损限制（%）

# Monitoring Settings / 监控设置
monitoring:
  check_interval: 5         # Price check interval (seconds) / 价格检查间隔（秒）
  price_precision: 2         # Price precision / 价格精度
```

## Usage / 使用方法

### Command Line Mode / 命令行模式

```bash
# Basic usage / 基本用法
python run.py

# With testnet / 使用测试网
python run.py --testnet

# Custom config file / 自定义配置文件
python run.py --config my_config.yaml

# Debug mode / 调试模式
python run.py --log-level DEBUG
```

### Web Interface Mode / Web 界面模式

1. **Start backend server / 启动后端服务器:**

```bash
python -m uvicorn ftrader.web_server:app --host 0.0.0.0 --port 8000 --reload
```

2. **Start frontend dev server / 启动前端开发服务器:**

```bash
cd frontend
npm run dev
```

3. **Access the web interface / 访问 Web 界面:**

Open http://localhost:5173 in your browser.

4. **API Documentation / API 文档:**

Visit http://localhost:8000/docs for interactive API documentation.

## Strategy Templates / 策略模板

FTrader includes several pre-built strategy templates:

### 1. Martingale Strategy / 马丁格尔策略

A position-averaging strategy that increases position size when price moves against you.

**Features / 特点:**
- Configurable initial position size
- Exponential position multiplier
- Maximum addition limit
- Price drop trigger threshold

### 2. DCA (Dollar Cost Averaging) Strategy / DCA 定投策略

Regular fixed-amount investments at set intervals.

**Features / 特点:**
- Fixed investment amount per interval
- Configurable time intervals
- Price threshold filtering
- Maximum investment limit

### 3. Grid Trading Strategy / 网格交易策略

Buy low and sell high within a price range using grid orders.

**Features / 特点:**
- Configurable grid count and spacing
- Automatic order placement
- Price range boundaries
- Order amount per grid

### 4. Trend Following Strategy / 趋势跟踪策略

Follows market trends using moving averages.

**Features / 特点:**
- Dual moving average system
- Trend confirmation mechanism
- Automatic entry/exit signals

### 5. Mean Reversion Strategy / 均值回归策略

Takes advantage of price deviations from the mean.

**Features / 特点:**
- Moving average baseline
- Deviation threshold
- Reversion target

## Web Interface / Web 界面

The web interface provides a comprehensive trading management system:

### Dashboard / 仪表板

- Real-time account balance and P&L
- Strategy status overview
- Recent trades and events

### Strategy Management / 策略管理

- Create new strategies from templates
- Edit existing strategy configurations
- Start/stop strategies
- View strategy details and performance

### Account Management / 账户管理

- Account balance and equity
- P&L charts and statistics
- Position list
- Trading history

### Real-time Updates / 实时更新

- WebSocket-based real-time data push
- Strategy status changes
- Trade execution notifications
- Account balance updates

## Project Structure / 项目结构

```
ftrader/
├── frontend/                 # Frontend web application / 前端 Web 应用
│   ├── src/
│   │   ├── api/             # API client / API 客户端
│   │   ├── views/           # Vue components / Vue 组件
│   │   └── main.ts          # Entry point / 入口文件
│   └── package.json
├── src/
│   └── ftrader/
│       ├── api/             # FastAPI routes / FastAPI 路由
│       ├── models/          # Database models / 数据库模型
│       ├── strategies/      # Strategy implementations / 策略实现
│       ├── config.py        # Configuration management / 配置管理
│       ├── database.py      # Database setup / 数据库设置
│       ├── exchange.py      # Exchange wrapper / 交易所封装
│       ├── risk_manager.py  # Risk management / 风险管理
│       ├── strategy_manager.py  # Strategy manager / 策略管理器
│       ├── strategy_templates.py  # Strategy templates / 策略模板
│       ├── web_server.py    # Web server / Web 服务器
│       └── main.py          # CLI entry point / CLI 入口
├── database/                # SQLite database files / SQLite 数据库文件
├── config.yaml              # Example strategy config / 示例策略配置
├── .env.example             # Environment variables template / 环境变量模板
├── pyproject.toml           # Project configuration / 项目配置
└── README.md                # This file / 本文件
```

## Requirements / 依赖要求

### Backend Dependencies / 后端依赖

- Python 3.9+
- ccxt >= 4.0.0
- pyyaml >= 6.0
- python-dotenv >= 1.0.0
- fastapi >= 0.104.0
- uvicorn[standard] >= 0.24.0
- sqlalchemy >= 2.0.0
- websockets >= 12.0
- pydantic >= 2.0.0

### Frontend Dependencies / 前端依赖

- Node.js 16+
- Vue 3
- Element Plus
- ECharts
- Axios
- Pinia
- Vue Router

## Disclaimer / 免责声明

⚠️ **IMPORTANT RISK WARNING / 重要风险提示**

1. **High Risk Trading / 高风险交易**: Cryptocurrency futures trading involves substantial risk of loss. Only trade with funds you can afford to lose.

2. **No Guarantees / 无保证**: This software is provided "as is" without any warranties. Past performance does not guarantee future results.

3. **Test Thoroughly / 充分测试**: Always test strategies on testnet before using real funds. Use testnet API keys for development and testing.

4. **Leverage Risk / 杠杆风险**: Leverage trading amplifies both profits and losses. Use leverage cautiously.

5. **Educational Purpose / 教育目的**: This framework is for educational and research purposes. Use at your own risk.

6. **Not Financial Advice / 非财务建议**: This software does not constitute financial advice. Always do your own research.

**The authors and contributors are not responsible for any financial losses incurred from using this software.**

## Contributing / 贡献

Contributions are welcome! Please feel free to submit a Pull Request.

欢迎贡献！请随时提交 Pull Request。

## License / 许可证

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

---

**Made with ❤️ for the crypto trading community**

**为加密货币交易社区用心打造**

# FTrader Web系统使用说明

## 功能特性

- ✅ 多策略管理：支持同时运行多个交易策略
- ✅ 策略配置：通过YAML配置文件创建策略
- ✅ Web可视化界面：实时监控策略状态和账户信息
- ✅ 实时数据推送：WebSocket实时推送策略状态和交易事件
- ✅ 数据持久化：SQLite数据库存储策略配置、交易记录、账户快照
- ✅ 图表展示：ECharts图表展示收益曲线、价格走势等

## 安装和运行

### 1. 安装后端依赖

```bash
pip install -e .
```

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 配置环境变量

创建 `.env` 文件并配置币安API密钥：

```
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key
BINANCE_TESTNET=false
```

### 4. 启动后端服务

```bash
python -m uvicorn ftrader.web_server:app --host 0.0.0.0 --port 8000 --reload
```

或者：

```bash
python -m ftrader.web_server
```

### 5. 启动前端开发服务器

```bash
cd frontend
npm run dev
```

### 6. 访问Web界面

打开浏览器访问：http://localhost:5173

## 使用说明

### 创建策略

1. 进入"策略管理"页面
2. 点击"创建策略"按钮
3. 填写策略名称和描述
4. 在"配置YAML"文本框中输入策略配置，例如：

```yaml
trading:
  symbol: "BTC/USDT:USDT"
  side: "long"
  leverage: 10

martingale:
  initial_position: 200
  multiplier: 2.0
  max_additions: 5

trigger:
  price_drop_percent: 5.0
  start_immediately: true

risk:
  stop_loss_percent: 10.0
  take_profit_percent: 15.0
  max_loss_percent: 20.0

monitoring:
  check_interval: 5
  price_precision: 2
```

5. 点击"保存"创建策略

### 启动/停止策略

在策略列表中，点击"启动"或"停止"按钮来控制策略运行。

### 查看策略详情

点击策略列表中的"查看"按钮，可以查看：
- 策略基本信息
- 价格图表
- 交易记录
- 策略状态

### 账户管理

在"账户"页面可以查看：
- 账户余额
- 收益曲线
- 持仓列表
- 交易历史

## API文档

启动服务后，访问 http://localhost:8000/docs 查看Swagger API文档。

## 注意事项

1. 首次运行会自动创建SQLite数据库文件（`database/ftrader.db`）
2. 建议在测试网环境下测试策略
3. 策略运行时会定期保存账户快照（每分钟一次）
4. WebSocket连接会自动重连，最多重试5次

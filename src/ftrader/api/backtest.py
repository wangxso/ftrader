"""回测API模块"""

import logging
import yaml
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models.strategy import Strategy
from ..models.backtest import BacktestResult, BacktestStatus
from ..backtester import Backtester
from ..exchange_manager import get_exchange
from ..strategies.martingale import MartingaleStrategy
from ..strategies.random_forest import RandomForestStrategy
from ..strategies.llm_strategy import LLMStrategy
from ..api.websocket import broadcast_backtest_progress
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["回测"])


class BacktestRequest(BaseModel):
    """回测请求"""
    strategy_id: int
    start_date: str  # ISO格式日期字符串
    end_date: str  # ISO格式日期字符串
    initial_balance: float = 10000.0
    symbol: Optional[str] = None  # 如果为空，从策略配置中获取
    timeframe: str = '1m'  # 时间周期


class BacktestResponse(BaseModel):
    """回测响应"""
    id: int
    strategy_id: int
    status: str
    initial_balance: float
    final_balance: Optional[float]
    total_return: Optional[float]
    total_trades: int
    win_rate: Optional[float]
    max_drawdown: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]


class BacktestDetailResponse(BacktestResponse):
    """回测详情响应"""
    start_date: datetime
    end_date: datetime
    symbol: str
    timeframe: str
    total_return_amount: Optional[float]
    win_trades: int
    loss_trades: int
    sharpe_ratio: Optional[float]
    profit_factor: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]
    equity_curve: Optional[List[Dict]]
    trades: Optional[List[Dict]]
    price_data: Optional[List[Dict]] = None  # 价格趋势数据


def _run_backtest(backtest_id: int, strategy_id: int, start_date: datetime, 
                  end_date: datetime, initial_balance: float, symbol: str,
                  timeframe: str, strategy_config: Dict[str, Any], db: Session):
    """在后台运行回测"""
    try:
        # 更新状态为运行中
        backtest = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
        if not backtest:
            logger.error(f"回测记录 {backtest_id} 不存在")
            return
        
        backtest.status = BacktestStatus.RUNNING
        db.commit()
        
        # 获取交易所实例（用于获取历史数据）
        exchange = get_exchange()
        
        # 计算需要获取的K线数量
        timeframes = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '30m': timedelta(minutes=30),
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1),
        }
        timeframe_delta = timeframes.get(timeframe, timedelta(minutes=1))
        total_duration = end_date - start_date
        limit = int(total_duration / timeframe_delta) + 100  # 多获取一些数据
        
        logger.info(f"开始获取历史数据: {symbol}, {timeframe}, 从 {start_date} 到 {end_date}")
        
        # 计算时间戳
        start_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        
        # 获取历史K线数据（使用since参数）
        # 优先尝试获取1分钟数据，然后展开为秒级数据以获得更高精度
        ohlcv_data = []
        current_since = start_timestamp
        max_candles_per_request = 1000  # CCXT通常限制每次最多1000条
        
        # 如果时间周期大于1分钟，先获取1分钟数据，然后展开为秒级
        # 这样可以获得更精确的回测结果
        fetch_timeframe = timeframe
        if timeframe not in ['1m']:
            # 对于大于1分钟的时间周期，先获取1分钟数据
            fetch_timeframe = '1m'
            logger.info(f"时间周期 {timeframe} 大于1分钟，将获取1分钟数据并展开为秒级数据")
        
        while current_since < end_timestamp:
            try:
                # 使用fetch_ohlcv获取历史数据
                batch = exchange.exchange.fetch_ohlcv(
                    symbol, 
                    fetch_timeframe,  # 使用fetch_timeframe（可能是1m）
                    since=current_since,
                    limit=max_candles_per_request
                )
                
                if not batch:
                    break
                
                # 过滤到结束时间
                batch_filtered = [
                    candle for candle in batch
                    if start_timestamp <= candle[0] <= end_timestamp
                ]
                
                ohlcv_data.extend(batch_filtered)
                
                # 如果返回的数据少于请求的数量，说明已经获取完所有数据
                if len(batch) < max_candles_per_request:
                    break
                
                # 更新since为最后一条数据的时间戳
                current_since = batch[-1][0] + 1
                
                # 如果最后一条数据已经超过结束时间，停止
                if batch[-1][0] >= end_timestamp:
                    break
                    
            except Exception as e:
                logger.warning(f"获取历史数据批次失败: {e}")
                break
        
        # 去重并排序
        if ohlcv_data:
            # 按时间戳去重
            seen = set()
            unique_data = []
            for candle in ohlcv_data:
                if candle[0] not in seen:
                    seen.add(candle[0])
                    unique_data.append(candle)
            ohlcv_data = sorted(unique_data, key=lambda x: x[0])
        
        if not ohlcv_data:
            raise ValueError("指定时间范围内没有数据")
        
        logger.info(f"获取到 {len(ohlcv_data)} 条 {fetch_timeframe} K线数据")
        
        # 将所有K线数据展开为秒级数据，确保回测精确到秒级别
        from ..backtester import expand_ohlcv_to_seconds
        original_count = len(ohlcv_data)
        ohlcv_data = expand_ohlcv_to_seconds(ohlcv_data, fetch_timeframe)
        logger.info(f"已展开为秒级数据: {original_count} 条 {fetch_timeframe} K线 -> {len(ohlcv_data)} 条秒级数据点")
        
        # 根据配置自动识别策略类型
        strategy_class = None
        
        # 优先检查顶层的策略标识字段
        if 'llm' in strategy_config:
            logger.info("检测到顶层llm配置，使用LLM多因子策略")
            strategy_class = LLMStrategy
        elif 'ml' in strategy_config or 'random_forest' in strategy_config:
            logger.info("检测到顶层ml/random_forest配置，使用随机森林策略")
            strategy_class = RandomForestStrategy
        elif 'martingale' in strategy_config:
            logger.info("检测到顶层martingale配置，使用马丁格尔策略")
            strategy_class = MartingaleStrategy
        elif 'trading' in strategy_config:
            # 检查trading字段下的配置
            trading_config = strategy_config.get('trading', {})
            if 'llm' in trading_config:
                logger.info("检测到trading.llm配置，使用LLM多因子策略")
                strategy_class = LLMStrategy
            elif 'ml' in trading_config:
                logger.info("检测到trading.ml配置，使用随机森林策略")
                strategy_class = RandomForestStrategy
            else:
                logger.info("检测到trading配置但无策略标识，默认使用马丁格尔策略")
                strategy_class = MartingaleStrategy
        else:
            logger.warning("未找到策略标识字段，默认使用马丁格尔策略")
            strategy_class = MartingaleStrategy
        
        if strategy_class is None:
            raise ValueError("无法识别策略类型，请检查配置文件中是否包含 llm、ml 或 martingale 字段")
        
        # 创建进度回调函数
        def progress_callback(current: int, total: int, percentage: float, current_balance: float):
            """回测进度回调"""
            broadcast_backtest_progress(backtest_id, current, total, percentage, current_balance)
        
        # 创建回测引擎
        backtester = Backtester(
            strategy_class=strategy_class,
            strategy_config=strategy_config,
            ohlcv_data=ohlcv_data,
            initial_balance=initial_balance,
            progress_callback=progress_callback
        )
        
        # 运行回测
        results = backtester.run()
        
        # 更新回测结果
        backtest.final_balance = results['final_balance']
        backtest.total_return = results['total_return']
        backtest.total_return_amount = results['total_return_amount']
        backtest.total_trades = results['total_trades']
        backtest.win_trades = results['win_trades']
        backtest.loss_trades = results['loss_trades']
        backtest.win_rate = results['win_rate']
        backtest.max_drawdown = results['max_drawdown']
        backtest.max_drawdown_amount = results['max_drawdown_amount']
        backtest.sharpe_ratio = results['sharpe_ratio']
        backtest.profit_factor = results['profit_factor']
        backtest.avg_win = results['avg_win']
        backtest.avg_loss = results['avg_loss']
        backtest.avg_trade_return = results['avg_trade_return']
        backtest.equity_curve = results['equity_curve']
        backtest.trades_data = results['trades']
        
        # 保存价格数据（如果存在）
        if 'price_data' in results and results['price_data']:
            price_data = results['price_data']
            logger.info(f"准备保存价格数据: {len(price_data)} 条记录")
            
            # 将价格数据存储到parameters中
            # 确保parameters是一个可修改的字典
            if backtest.parameters is None:
                backtest.parameters = {}
            elif not isinstance(backtest.parameters, dict):
                # 如果parameters不是字典，尝试转换
                logger.warning(f"parameters类型不是dict: {type(backtest.parameters)}，尝试转换")
                try:
                    import json
                    if isinstance(backtest.parameters, str):
                        backtest.parameters = json.loads(backtest.parameters)
                    else:
                        # 创建一个新字典
                        original_params = backtest.parameters
                        backtest.parameters = {}
                        # 尝试保留原有配置
                        if hasattr(original_params, '__dict__'):
                            backtest.parameters.update(original_params.__dict__)
                except Exception as e:
                    logger.error(f"转换parameters失败: {e}，创建新字典")
                    backtest.parameters = {}
            
            # 保存价格数据（限制数据量，避免数据库过大）
            # 如果数据点太多，进行采样（每10个点取1个）
            if len(price_data) > 10000:
                logger.info(f"价格数据点过多({len(price_data)})，进行采样（每10个点取1个）")
                sample_rate = max(1, len(price_data) // 10000)
                price_data = price_data[::sample_rate]
                logger.info(f"采样后数据点: {len(price_data)}")
            
            # 保存价格数据
            backtest.parameters['price_data'] = price_data
            # 标记JSON字段已修改，确保SQLAlchemy正确保存
            flag_modified(backtest, 'parameters')
            logger.info(f"价格数据已保存到parameters，共 {len(price_data)} 条记录")
            
            # 验证保存
            if backtest.parameters.get('price_data'):
                logger.info(f"验证：parameters中price_data数量: {len(backtest.parameters['price_data'])}")
            else:
                logger.error("警告：保存后无法从parameters中读取price_data")
        else:
            logger.warning(f"回测结果中没有price_data字段或price_data为空。results keys: {list(results.keys())}")
        
        backtest.status = BacktestStatus.COMPLETED
        backtest.completed_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"回测 {backtest_id} 完成，价格数据已保存")
        
    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        try:
            backtest = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
            if backtest:
                backtest.status = BacktestStatus.FAILED
                backtest.error_message = str(e)
                db.commit()
        except Exception as commit_error:
            logger.error(f"更新回测状态失败: {commit_error}")


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """运行回测"""
    # 获取策略
    strategy = db.query(Strategy).filter(Strategy.id == request.strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    # 解析日期
    try:
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"日期格式错误: {e}")
    
    if start_date >= end_date:
        raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")
    
    # 获取交易对
    symbol = request.symbol
    if not symbol:
        try:
            config = yaml.safe_load(strategy.config_yaml or '{}')
            symbol = config.get('trading', {}).get('symbol', 'BTC/USDT:USDT')
        except:
            symbol = 'BTC/USDT:USDT'
    
    # 获取策略配置
    try:
        strategy_config = yaml.safe_load(strategy.config_yaml or '{}')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"策略配置解析失败: {e}")
    
    # 创建回测记录
    backtest = BacktestResult(
        strategy_id=request.strategy_id,
        start_date=start_date,
        end_date=end_date,
        initial_balance=request.initial_balance,
        symbol=symbol,
        timeframe=request.timeframe,
        parameters=strategy_config,
        status=BacktestStatus.PENDING
    )
    
    db.add(backtest)
    db.commit()
    db.refresh(backtest)
    
    # 在后台运行回测
    background_tasks.add_task(
        _run_backtest,
        backtest.id,
        request.strategy_id,
        start_date,
        end_date,
        request.initial_balance,
        symbol,
        request.timeframe,
        strategy_config,
        db
    )
    
    return BacktestResponse(
        id=backtest.id,
        strategy_id=backtest.strategy_id,
        status=backtest.status.value,
        initial_balance=backtest.initial_balance,
        final_balance=backtest.final_balance,
        total_return=backtest.total_return,
        total_trades=backtest.total_trades,
        win_rate=backtest.win_rate,
        max_drawdown=backtest.max_drawdown,
        created_at=backtest.created_at,
        completed_at=backtest.completed_at
    )


@router.get("/results", response_model=List[BacktestResponse])
async def get_backtest_results(
    strategy_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取回测结果列表"""
    query = db.query(BacktestResult)
    
    if strategy_id:
        query = query.filter(BacktestResult.strategy_id == strategy_id)
    
    backtests = query.order_by(BacktestResult.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        BacktestResponse(
            id=bt.id,
            strategy_id=bt.strategy_id,
            status=bt.status.value,
            initial_balance=bt.initial_balance,
            final_balance=bt.final_balance,
            total_return=bt.total_return,
            total_trades=bt.total_trades,
            win_rate=bt.win_rate,
            max_drawdown=bt.max_drawdown,
            created_at=bt.created_at,
            completed_at=bt.completed_at
        )
        for bt in backtests
    ]


@router.get("/results/{backtest_id}", response_model=BacktestDetailResponse)
async def get_backtest_detail(
    backtest_id: int,
    db: Session = Depends(get_db)
):
    """获取回测详情"""
    backtest = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    if not backtest:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    
    # 从parameters中提取价格数据
    price_data = None
    if backtest.parameters:
        try:
            if isinstance(backtest.parameters, dict):
                price_data = backtest.parameters.get('price_data')
                logger.info(f"从parameters中提取价格数据: {len(price_data) if price_data else 0} 条记录")
            elif isinstance(backtest.parameters, str):
                # 如果是字符串，尝试解析JSON
                import json
                params_dict = json.loads(backtest.parameters)
                price_data = params_dict.get('price_data')
                logger.info(f"从JSON字符串中提取价格数据: {len(price_data) if price_data else 0} 条记录")
            else:
                logger.warning(f"parameters类型不是dict或str: {type(backtest.parameters)}")
                # 尝试转换为字典
                try:
                    if hasattr(backtest.parameters, 'get'):
                        price_data = backtest.parameters.get('price_data')
                    elif hasattr(backtest.parameters, '__dict__'):
                        price_data = backtest.parameters.__dict__.get('price_data')
                except Exception as e:
                    logger.error(f"转换parameters失败: {e}")
        except Exception as e:
            logger.error(f"提取价格数据时出错: {e}", exc_info=True)
    
    logger.info(f"返回回测详情，price_data: {'存在' if price_data else '不存在'}, 数量: {len(price_data) if price_data else 0}")
    
    return BacktestDetailResponse(
        id=backtest.id,
        strategy_id=backtest.strategy_id,
        status=backtest.status.value,
        start_date=backtest.start_date,
        end_date=backtest.end_date,
        initial_balance=backtest.initial_balance,
        final_balance=backtest.final_balance,
        total_return=backtest.total_return,
        total_return_amount=backtest.total_return_amount,
        total_trades=backtest.total_trades,
        win_trades=backtest.win_trades,
        loss_trades=backtest.loss_trades,
        win_rate=backtest.win_rate,
        max_drawdown=backtest.max_drawdown,
        sharpe_ratio=backtest.sharpe_ratio,
        profit_factor=backtest.profit_factor,
        avg_win=backtest.avg_win,
        avg_loss=backtest.avg_loss,
        symbol=backtest.symbol,
        timeframe=backtest.timeframe,
        equity_curve=backtest.equity_curve,
        trades=backtest.trades_data,
        price_data=price_data,  # 添加价格数据
        created_at=backtest.created_at,
        completed_at=backtest.completed_at
    )


@router.delete("/results/{backtest_id}")
async def delete_backtest_result(
    backtest_id: int,
    db: Session = Depends(get_db)
):
    """删除回测结果"""
    backtest = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    if not backtest:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    
    db.delete(backtest)
    db.commit()
    
    return {"message": "回测结果已删除"}


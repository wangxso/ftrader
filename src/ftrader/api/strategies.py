"""策略管理API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from ..database import get_db
from ..models.strategy import Strategy, StrategyRun, StrategyStatus, StrategyType
from ..strategy_manager import get_strategy_manager
from ..exchange import BinanceExchange
import yaml
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyCreate(BaseModel):
    """创建策略请求"""
    name: str
    description: Optional[str] = None
    strategy_type: str = "config"
    config_yaml: Optional[str] = None
    code_path: Optional[str] = None
    code_content: Optional[str] = None
    class_name: Optional[str] = None


class StrategyUpdate(BaseModel):
    """更新策略请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    config_yaml: Optional[str] = None
    code_path: Optional[str] = None
    code_content: Optional[str] = None
    class_name: Optional[str] = None


class StrategyResponse(BaseModel):
    """策略响应"""
    id: int
    name: str
    description: Optional[str]
    strategy_type: str
    status: str
    config_yaml: Optional[str] = None  # 配置YAML（编辑时需要）
    code_path: Optional[str] = None
    code_content: Optional[str] = None
    class_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[StrategyResponse])
async def get_strategies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取所有策略列表"""
    strategies = db.query(Strategy).offset(skip).limit(limit).all()
    return strategies


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """获取单个策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return strategy


@router.post("", response_model=StrategyResponse)
async def create_strategy(strategy_data: StrategyCreate, db: Session = Depends(get_db)):
    """创建新策略"""
    # 验证配置
    if strategy_data.strategy_type == "config" and not strategy_data.config_yaml:
        raise HTTPException(status_code=400, detail="配置型策略必须提供config_yaml")
    
    if strategy_data.strategy_type == "code" and not strategy_data.code_content and not strategy_data.code_path:
        raise HTTPException(status_code=400, detail="代码型策略必须提供code_content或code_path")
    
    # 验证YAML格式
    if strategy_data.config_yaml:
        try:
            yaml.safe_load(strategy_data.config_yaml)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"YAML格式错误: {e}")
    
    strategy = Strategy(
        name=strategy_data.name,
        description=strategy_data.description,
        strategy_type=StrategyType(strategy_data.strategy_type),
        config_yaml=strategy_data.config_yaml,
        code_path=strategy_data.code_path,
        code_content=strategy_data.code_content,
        class_name=strategy_data.class_name,
        status=StrategyStatus.STOPPED
    )
    
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    
    return strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    strategy_data: StrategyUpdate,
    db: Session = Depends(get_db)
):
    """更新策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    # 检查策略是否在运行
    if strategy.status == StrategyStatus.RUNNING:
        raise HTTPException(status_code=400, detail="运行中的策略无法修改，请先停止")
    
    # 更新字段
    if strategy_data.name is not None:
        strategy.name = strategy_data.name
    if strategy_data.description is not None:
        strategy.description = strategy_data.description
    if strategy_data.config_yaml is not None:
        # 验证YAML格式
        try:
            yaml.safe_load(strategy_data.config_yaml)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"YAML格式错误: {e}")
        strategy.config_yaml = strategy_data.config_yaml
    if strategy_data.code_path is not None:
        strategy.code_path = strategy_data.code_path
    if strategy_data.code_content is not None:
        strategy.code_content = strategy_data.code_content
    if strategy_data.class_name is not None:
        strategy.class_name = strategy_data.class_name
    
    strategy.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(strategy)
    
    return strategy


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """删除策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    # 检查策略是否在运行
    if strategy.status == StrategyStatus.RUNNING:
        raise HTTPException(status_code=400, detail="运行中的策略无法删除，请先停止")
    
    # 停止策略（如果在运行）
    manager = get_strategy_manager()
    if strategy_id in manager.strategies:
        await manager.stop_strategy(strategy_id)
    
    db.delete(strategy)
    db.commit()
    
    return {"message": "策略已删除"}


@router.post("/{strategy_id}/start")
async def start_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """启动策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    if strategy.status == StrategyStatus.RUNNING:
        raise HTTPException(status_code=400, detail="策略已在运行")
    
    manager = get_strategy_manager()
    success = await manager.start_strategy(strategy_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="启动策略失败")
    
    return {"message": "策略已启动"}


@router.post("/{strategy_id}/stop")
async def stop_strategy(
    strategy_id: int, 
    close_positions: bool = True,
    db: Session = Depends(get_db)
):
    """
    停止策略
    
    Args:
        strategy_id: 策略ID
        close_positions: 是否在停止前平仓，默认为True
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    # 如果策略状态不是 RUNNING，直接返回成功（可能已经停止了）
    if strategy.status != StrategyStatus.RUNNING:
        return {"message": "策略未在运行，无需停止"}
    
    manager = get_strategy_manager()
    success = await manager.stop_strategy(strategy_id, close_positions=close_positions)
    
    if not success:
        # 即使停止失败，也尝试更新数据库状态（修复状态不同步）
        try:
            strategy.status = StrategyStatus.STOPPED
            db.commit()
            logger.warning(f"策略停止失败，但已更新数据库状态: {strategy_id}")
        except Exception as e:
            logger.error(f"更新策略状态失败: {e}")
            db.rollback()
        raise HTTPException(status_code=500, detail="停止策略失败，但已尝试修复状态")
    
    return {"message": "策略已停止" + ("，持仓已平仓" if close_positions else "")}


@router.get("/{strategy_id}/status")
async def get_strategy_status(strategy_id: int, db: Session = Depends(get_db)):
    """获取策略状态（包含持仓信息和当前运行记录ID）"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    manager = get_strategy_manager()
    status = manager.get_strategy_status(strategy_id)
    
    if not status:
        raise HTTPException(status_code=500, detail="获取策略状态失败")
    
    # 获取当前运行记录ID（如果策略正在运行）
    current_run_id = None
    if strategy.status == StrategyStatus.RUNNING:
        run = db.query(StrategyRun).filter(
            StrategyRun.strategy_id == strategy_id,
            StrategyRun.status == StrategyStatus.RUNNING
        ).order_by(StrategyRun.started_at.desc()).first()
        if run:
            current_run_id = run.id
    
    status['current_run_id'] = current_run_id
    
    # 获取持仓信息
    position_info = None
    if strategy_id in manager.strategies:
        try:
            strategy_instance = manager.strategies[strategy_id]
            exchange = strategy_instance.exchange
            symbol = strategy_instance.symbol
            
            position = exchange.get_open_position(symbol)
            if position:
                contracts = abs(position.get('contracts', 0))
                if contracts > 0:
                    position_info = {
                        'symbol': symbol,
                        'side': position.get('side', ''),
                        'contracts': contracts,
                        'entry_price': position.get('entryPrice', 0),
                        'current_price': position.get('markPrice') or position.get('lastPrice', 0),
                        'unrealized_pnl': position.get('unrealizedPnl', 0),
                        'unrealized_pnl_percent': position.get('unrealizedPnlPercent', 0),
                    }
        except Exception as e:
            logger.warning(f"获取策略持仓信息失败: {e}")
    
    status['position'] = position_info
    return status


@router.get("/runs/all")
async def get_all_strategy_runs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取所有策略的运行记录（历史策略）"""
    from ..models.trade import Trade
    from sqlalchemy import func
    
    runs = db.query(StrategyRun).join(Strategy).order_by(
        StrategyRun.started_at.desc()
    ).offset(skip).limit(limit).all()
    
    # 包含策略信息和计算的总盈亏
    result = []
    for run in runs:
        # 计算该运行记录关联的所有交易的盈亏总和
        # 只计算平仓交易的 pnl（因为开仓和加仓交易没有 pnl）
        total_pnl = db.query(func.sum(Trade.pnl)).filter(
            Trade.strategy_run_id == run.id,
            Trade.pnl.isnot(None)  # 只计算有盈亏的交易（平仓交易）
        ).scalar() or 0.0
        
        run_dict = {
            "id": run.id,
            "strategy_id": run.strategy_id,
            "strategy_name": run.strategy.name if run.strategy else None,
            "status": run.status.value if isinstance(run.status, StrategyStatus) else str(run.status),
            "start_balance": run.start_balance,
            "current_balance": run.current_balance,
            "total_pnl": total_pnl,  # 通过交易记录计算的总盈亏
            "total_trades": run.total_trades,
            "win_trades": run.win_trades,
            "loss_trades": run.loss_trades,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "stopped_at": run.stopped_at.isoformat() if run.stopped_at else None,
            "error_message": run.error_message,
        }
        result.append(run_dict)
    
    return result


@router.get("/{strategy_id}/runs")
async def get_strategy_runs(strategy_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取策略运行记录"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    runs = db.query(StrategyRun).filter(
        StrategyRun.strategy_id == strategy_id
    ).order_by(StrategyRun.started_at.desc()).offset(skip).limit(limit).all()
    
    return runs


@router.post("/{strategy_id}/retrain")
async def retrain_strategy_model(strategy_id: int, force: bool = False, db: Session = Depends(get_db)):
    """手动触发策略模型重新训练（仅适用于机器学习策略）"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    manager = get_strategy_manager()
    
    # 检查策略是否在运行
    if strategy_id not in manager.strategies:
        raise HTTPException(status_code=400, detail="策略未在运行，无法重新训练模型")
    
    strategy_instance = manager.strategies[strategy_id]
    
    # 检查是否是随机森林策略
    from ..strategies.random_forest import RandomForestStrategy
    if not isinstance(strategy_instance, RandomForestStrategy):
        raise HTTPException(status_code=400, detail="此策略不支持模型重新训练")
    
    # 触发重新训练
    try:
        result = await strategy_instance.retrain_model(force=force)
        
        if result.get('success'):
            return {
                "message": result.get('message', '模型重新训练成功'),
                "last_retrain_time": result.get('last_retrain_time'),
                "training_samples": result.get('training_samples')
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('message', '重新训练失败'))
            
    except Exception as e:
        logger.error(f"重新训练模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重新训练失败: {str(e)}")


@router.get("/{strategy_id}/price-history")
async def get_strategy_price_history(
    strategy_id: int,
    timeframe: str = '1m',
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取策略的价格历史数据（用于图表）"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    # 从配置中获取交易对
    try:
        config = yaml.safe_load(strategy.config_yaml or '{}')
        symbol = config.get('trading', {}).get('symbol', 'BTC/USDT:USDT')
    except:
        symbol = 'BTC/USDT:USDT'
    
    # 获取交易所实例
    manager = get_strategy_manager()
    exchange = None
    
    if manager.exchanges:
        exchange = list(manager.exchanges.values())[0]
    else:
        # 如果没有策略运行，创建默认交易所实例
        use_testnet = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
        if use_testnet:
            api_key = os.getenv('BINANCE_TESTNET_API_KEY') or os.getenv('BINANCE_API_KEY', '')
            api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY', '')
        else:
            api_key = os.getenv('BINANCE_API_KEY', '')
            api_secret = os.getenv('BINANCE_SECRET_KEY', '')
        
        if api_key and api_secret:
            exchange = BinanceExchange(api_key, api_secret, testnet=use_testnet)
    
    if not exchange:
        # 如果没有交易所实例，返回空数据
        return []
    
    # 获取K线数据
    try:
        ohlcv = exchange.get_ohlcv(symbol, timeframe, limit)
        # 转换为前端需要的格式
        result = []
        for candle in ohlcv:
            result.append({
                'timestamp': candle[0],  # 时间戳
                'time': candle[0],  # 时间戳（兼容）
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5],
            })
        return result
    except Exception as e:
        logger.error(f"获取价格历史失败: {e}", exc_info=True)
        return []

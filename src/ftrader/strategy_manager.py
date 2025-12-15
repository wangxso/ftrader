"""策略管理器模块"""

import os
import logging
import asyncio
import yaml
from typing import Dict, Optional, List, Any, Callable
from datetime import datetime
from sqlalchemy.orm import Session

from .database import get_db, SessionLocal
from .models.strategy import Strategy, StrategyRun, StrategyStatus, StrategyType
from .models.trade import Trade, TradeType, TradeSide
from .models.position import Position, PositionSide
from .models.account import AccountSnapshot
from .exchange import BinanceExchange
from .exchange_manager import get_exchange
from .risk_manager import RiskManager
from .config import Config
from .strategies.base import BaseStrategy
from .strategies.martingale import MartingaleStrategy
from .strategies.random_forest import RandomForestStrategy

logger = logging.getLogger(__name__)


class StrategyManager:
    """策略管理器，负责管理多个策略的注册、启动、停止等"""
    
    def __init__(self):
        """初始化策略管理器"""
        self.strategies: Dict[int, BaseStrategy] = {}  # 运行中的策略实例
        self.strategy_tasks: Dict[int, asyncio.Task] = {}  # 策略运行任务
        self.exchanges: Dict[int, BinanceExchange] = {}  # 每个策略的交易所实例
        self.risk_managers: Dict[int, RiskManager] = {}  # 每个策略的风险管理器
        
        # 回调函数
        self.on_strategy_status_change: Optional[Callable] = None
        self.on_strategy_trade: Optional[Callable] = None
        self.on_strategy_error: Optional[Callable] = None
    
    def register_callbacks(self, 
                          on_status_change: Optional[Callable] = None,
                          on_trade: Optional[Callable] = None,
                          on_error: Optional[Callable] = None):
        """
        注册回调函数
        
        Args:
            on_status_change: 策略状态变化回调 (strategy_id, status)
            on_trade: 交易回调 (strategy_id, trade_data)
            on_error: 错误回调 (strategy_id, error_message)
        """
        self.on_strategy_status_change = on_status_change
        self.on_strategy_trade = on_trade
        self.on_strategy_error = on_error
    
    def _create_exchange(self, strategy_id: int, use_testnet: bool = False) -> BinanceExchange:
        """
        创建交易所实例（使用单例管理器）
        
        Args:
            strategy_id: 策略ID
            use_testnet: 是否使用测试网
            
        Returns:
            交易所实例
        """
        # 使用单例管理器获取exchange实例，确保所有策略共享同一个实例
        exchange = get_exchange(testnet=use_testnet)
        # 仍然保存到字典中以便兼容现有代码
        self.exchanges[strategy_id] = exchange
        return exchange
    
    def _create_risk_manager(self, strategy_id: int, exchange: BinanceExchange, config_dict: Dict[str, Any]) -> RiskManager:
        """
        创建风险管理器
        
        Args:
            strategy_id: 策略ID
            exchange: 交易所实例
            config_dict: 配置字典
            
        Returns:
            风险管理器
        """
        if strategy_id in self.risk_managers:
            return self.risk_managers[strategy_id]
        
        # 创建临时Config对象用于风险管理器
        class TempConfig:
            def __init__(self, config_dict):
                risk = config_dict.get('risk', {})
                self.stop_loss_percent = risk.get('stop_loss_percent', 10.0)
                self.take_profit_percent = risk.get('take_profit_percent', 15.0)
                self.max_loss_percent = risk.get('max_loss_percent', 20.0)
        
        temp_config = TempConfig(config_dict)
        risk_manager = RiskManager(exchange, temp_config)
        self.risk_managers[strategy_id] = risk_manager
        return risk_manager
    
    def _create_strategy_instance(self, strategy: Strategy, config_dict: Dict[str, Any]) -> Optional[BaseStrategy]:
        """
        创建策略实例
        
        Args:
            strategy: 策略数据库模型
            config_dict: 配置字典
            
        Returns:
            策略实例
        """
        use_testnet = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
        exchange = self._create_exchange(strategy.id, use_testnet)
        risk_manager = self._create_risk_manager(strategy.id, exchange, config_dict)
        
        # 根据策略类型创建实例
        if strategy.strategy_type == StrategyType.CONFIG:
            # 配置型策略
            if 'martingale' in config_dict:
                # 马丁格尔策略
                return MartingaleStrategy(strategy.id, exchange, risk_manager, config_dict)
            elif 'ml' in config_dict or 'random_forest' in config_dict:
                # 随机森林策略
                return RandomForestStrategy(strategy.id, exchange, risk_manager, config_dict)
            elif 'trading' in config_dict:
                # 根据配置判断策略类型
                # 如果有 ml 相关配置，使用随机森林策略
                if 'ml' in config_dict.get('trading', {}):
                    return RandomForestStrategy(strategy.id, exchange, risk_manager, config_dict)
                # 否则使用马丁格尔策略
                return MartingaleStrategy(strategy.id, exchange, risk_manager, config_dict)
            else:
                logger.error(f"未知的配置型策略: {strategy.name}")
                return None
        elif strategy.strategy_type == StrategyType.CODE:
            # 代码型策略（待实现）
            logger.warning("代码型策略暂未实现")
            return None
        else:
            logger.error(f"未知的策略类型: {strategy.strategy_type}")
            return None
    
    def _strategy_status_callback(self, strategy_id: int, status: str):
        """策略状态变化回调"""
        db = SessionLocal()
        try:
            strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strategy:
                strategy.status = StrategyStatus(status)
                db.commit()
            
            # 更新运行记录
            run = db.query(StrategyRun).filter(
                StrategyRun.strategy_id == strategy_id,
                StrategyRun.status.in_([StrategyStatus.RUNNING, StrategyStatus.PAUSED])
            ).order_by(StrategyRun.started_at.desc()).first()
            
            if run:
                run.status = StrategyStatus(status)
                if status == 'stopped' and run.stopped_at is None:
                    run.stopped_at = datetime.utcnow()
                db.commit()
            
            # 调用外部回调
            if self.on_strategy_status_change:
                self.on_strategy_status_change(strategy_id, status)
        except Exception as e:
            logger.error(f"更新策略状态失败: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _strategy_trade_callback(self, strategy_id: int, trade_data: Dict[str, Any]):
        """策略交易回调"""
        db = SessionLocal()
        try:
            # 保存交易记录
            trade = Trade(
                strategy_id=strategy_id,
                trade_type=TradeType(trade_data['trade_type']),
                side=TradeSide(trade_data['side']),
                symbol=trade_data['symbol'],
                price=trade_data['price'],
                amount=trade_data['amount'],
                order_id=trade_data.get('order_id'),
                pnl=trade_data.get('pnl'),
                pnl_percent=trade_data.get('pnl_percent'),
                executed_at=datetime.fromisoformat(trade_data['timestamp'].replace('Z', '+00:00'))
            )
            db.add(trade)
            db.commit()
            
            # 更新或创建持仓记录
            trade_type = trade_data['trade_type']
            symbol = trade_data['symbol']
            side = PositionSide(trade_data['side'])
            price = trade_data['price']
            amount = trade_data['amount']
            
            if trade_type in ['open', 'add']:
                # 查找或创建持仓
                position = db.query(Position).filter(
                    Position.strategy_id == strategy_id,
                    Position.symbol == symbol,
                    Position.side == side,
                    Position.is_closed == False
                ).first()
                
                if position:
                    # 更新现有持仓（加权平均价格）
                    total_notional = position.notional_value + amount
                    position.entry_price = (position.entry_price * position.notional_value + price * amount) / total_notional
                    position.notional_value = total_notional
                    position.contracts = position.contracts + (amount / price)  # 简化计算
                    position.updated_at = datetime.utcnow()
                else:
                    # 创建新持仓
                    # 获取交易所实例以获取当前价格和持仓信息
                    exchange = None
                    if strategy_id in self.strategies:
                        strategy_instance = self.strategies[strategy_id]
                        if hasattr(strategy_instance, 'exchange'):
                            exchange = strategy_instance.exchange
                    
                    current_price = price  # 默认使用交易价格
                    contracts = amount / price  # 简化计算（合约数量 = 名义价值 / 价格）
                    leverage = 1  # 默认杠杆
                    
                    # 尝试从交易所获取实际持仓信息
                    if exchange:
                        try:
                            exchange_position = exchange.get_open_position(symbol)
                            if exchange_position:
                                # 获取标记价格或最新价格
                                current_price = exchange_position.get('markPrice') or exchange_position.get('lastPrice') or price
                                # 获取实际合约数量
                                exchange_contracts = abs(exchange_position.get('contracts', 0))
                                if exchange_contracts > 0:
                                    contracts = exchange_contracts
                                # 获取杠杆
                                leverage = exchange_position.get('leverage', 1)
                        except Exception as e:
                            logger.warning(f"获取持仓信息失败: {e}")
                    
                    position = Position(
                        strategy_id=strategy_id,
                        symbol=symbol,
                        side=side,
                        entry_price=price,
                        current_price=current_price,
                        contracts=contracts,
                        notional_value=amount,
                        leverage=leverage,
                        is_closed=False
                    )
                    db.add(position)
                
                db.commit()
                
            elif trade_type == 'close':
                # 平仓：更新持仓为已平仓
                position = db.query(Position).filter(
                    Position.strategy_id == strategy_id,
                    Position.symbol == symbol,
                    Position.side == side,
                    Position.is_closed == False
                ).first()
                
                if position:
                    position.is_closed = True
                    position.closed_at = datetime.utcnow()
                    if trade_data.get('pnl') is not None:
                        # 如果有盈亏信息，可以更新（虽然平仓后不再需要）
                        pass
                    db.commit()
            
            # 更新策略运行统计
            run = db.query(StrategyRun).filter(
                StrategyRun.strategy_id == strategy_id,
                StrategyRun.status == StrategyStatus.RUNNING
            ).order_by(StrategyRun.started_at.desc()).first()
            
            if run:
                # 确保字段不为 None，如果是 None 则初始化为 0
                if run.total_trades is None:
                    run.total_trades = 0
                if run.win_trades is None:
                    run.win_trades = 0
                if run.loss_trades is None:
                    run.loss_trades = 0
                
                run.total_trades += 1
                
                # 处理 pnl，确保不是 None
                pnl = trade_data.get('pnl')
                if pnl is not None:
                    if pnl > 0:
                        run.win_trades += 1
                    elif pnl < 0:
                        run.loss_trades += 1
                
                db.commit()
            
            # 调用外部回调
            if self.on_strategy_trade:
                self.on_strategy_trade(strategy_id, trade_data)
        except Exception as e:
            logger.error(f"保存交易记录失败: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _strategy_error_callback(self, strategy_id: int, error_message: str):
        """策略错误回调"""
        db = SessionLocal()
        try:
            run = db.query(StrategyRun).filter(
                StrategyRun.strategy_id == strategy_id,
                StrategyRun.status == StrategyStatus.RUNNING
            ).order_by(StrategyRun.started_at.desc()).first()
            
            if run:
                run.status = StrategyStatus.ERROR
                run.error_message = error_message
                run.stopped_at = datetime.utcnow()
                db.commit()
            
            # 调用外部回调
            if self.on_strategy_error:
                self.on_strategy_error(strategy_id, error_message)
        except Exception as e:
            logger.error(f"更新错误信息失败: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def start_strategy(self, strategy_id: int) -> bool:
        """
        启动策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否成功启动
        """
        db = SessionLocal()
        try:
            strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if not strategy:
                logger.error(f"策略不存在: {strategy_id}")
                return False
            
            if strategy.status == StrategyStatus.RUNNING:
                logger.warning(f"策略已在运行: {strategy_id}")
                return True
            
            # 加载配置
            if strategy.config_yaml:
                config_dict = yaml.safe_load(strategy.config_yaml)
            else:
                logger.error(f"策略配置为空: {strategy_id}")
                return False
            
            # 创建策略实例
            strategy_instance = self._create_strategy_instance(strategy, config_dict)
            if not strategy_instance:
                logger.error(f"创建策略实例失败: {strategy_id}")
                return False
            
            # 设置回调
            strategy_instance.on_status_change = self._strategy_status_callback
            strategy_instance.on_trade = self._strategy_trade_callback
            strategy_instance.on_error = self._strategy_error_callback
            
            # 创建运行记录
            balance = self.exchanges[strategy_id].get_balance()
            start_balance = balance['total'] if balance else 0.0
            run = StrategyRun(
                strategy_id=strategy_id,
                status=StrategyStatus.RUNNING,
                start_balance=start_balance,
                started_at=datetime.utcnow()
            )
            db.add(run)
            
            # 更新策略状态
            strategy.status = StrategyStatus.RUNNING
            db.commit()
            
            # 启动策略任务
            task = asyncio.create_task(strategy_instance.run())
            self.strategies[strategy_id] = strategy_instance
            self.strategy_tasks[strategy_id] = task
            
            logger.info(f"策略已启动: {strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动策略失败: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()
    
    async def stop_strategy(self, strategy_id: int) -> bool:
        """
        停止策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否成功停止
        """
        # 如果策略在运行中，先停止它
        if strategy_id in self.strategies:
            try:
                # 停止策略实例
                strategy_instance = self.strategies[strategy_id]
                strategy_instance.is_active = False
                strategy_instance.is_running = False
                
                # 取消任务
                task = self.strategy_tasks.get(strategy_id)
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # 清理
                del self.strategies[strategy_id]
                if strategy_id in self.strategy_tasks:
                    del self.strategy_tasks[strategy_id]
                
                logger.info(f"策略实例已停止: {strategy_id}")
            except Exception as e:
                logger.error(f"停止策略实例失败: {e}", exc_info=True)
        
        # 无论策略是否在运行中，都更新数据库状态
        # 这样可以修复状态不同步的问题
        db = SessionLocal()
        try:
            strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strategy:
                # 如果数据库状态是 RUNNING，更新为 STOPPED
                if strategy.status == StrategyStatus.RUNNING:
                    strategy.status = StrategyStatus.STOPPED
                    logger.info(f"更新策略数据库状态为已停止: {strategy_id}")
                else:
                    logger.debug(f"策略数据库状态已经是 {strategy.status}，无需更新")
            
            # 更新运行记录
            run = db.query(StrategyRun).filter(
                StrategyRun.strategy_id == strategy_id,
                StrategyRun.status == StrategyStatus.RUNNING
            ).order_by(StrategyRun.started_at.desc()).first()
            
            if run:
                # 尝试获取余额（如果交易所实例存在）
                balance = None
                if strategy_id in self.exchanges:
                    try:
                        balance = self.exchanges[strategy_id].get_balance()
                    except Exception as e:
                        logger.warning(f"获取余额失败: {e}")
                
                run.status = StrategyStatus.STOPPED
                run.current_balance = balance['total'] if balance else run.start_balance
                run.stopped_at = datetime.utcnow()
                logger.info(f"更新策略运行记录为已停止: {strategy_id}")
            
            db.commit()
            logger.info(f"策略已停止: {strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新策略状态失败: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()
    
    def get_strategy_status(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """
        获取策略状态
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            策略状态字典
        """
        if strategy_id in self.strategies:
            return self.strategies[strategy_id].get_status()
        
        # 从数据库获取
        db = SessionLocal()
        try:
            strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strategy:
                return {
                    'strategy_id': strategy.id,
                    'name': strategy.name,
                    'status': strategy.status.value,
                    'is_active': False,
                    'is_running': False,
                }
            return None
        finally:
            db.close()
    
    def get_all_strategies_status(self) -> List[Dict[str, Any]]:
        """
        获取所有策略状态
        
        Returns:
            策略状态列表
        """
        db = SessionLocal()
        try:
            strategies = db.query(Strategy).all()
            result = []
            for strategy in strategies:
                status = self.get_strategy_status(strategy.id)
                if status:
                    result.append(status)
            return result
        finally:
            db.close()
    
    def recover_strategy_states(self):
        """
        恢复策略状态（服务启动时调用）
        将数据库中状态为 RUNNING 但实际未运行的策略状态重置为 STOPPED
        """
        db = SessionLocal()
        try:
            # 查找所有状态为 RUNNING 的策略
            running_strategies = db.query(Strategy).filter(
                Strategy.status == StrategyStatus.RUNNING
            ).all()
            
            if not running_strategies:
                logger.info("没有需要恢复的策略状态")
                return
            
            logger.info(f"发现 {len(running_strategies)} 个状态为 RUNNING 的策略，开始恢复状态...")
            
            for strategy in running_strategies:
                # 检查策略是否真的在运行（在内存中）
                if strategy.id not in self.strategies:
                    # 策略不在运行中，需要恢复状态
                    logger.info(f"恢复策略 {strategy.id} ({strategy.name}) 的状态：RUNNING -> STOPPED")
                    strategy.status = StrategyStatus.STOPPED
                    
                    # 更新运行记录
                    run = db.query(StrategyRun).filter(
                        StrategyRun.strategy_id == strategy.id,
                        StrategyRun.status == StrategyStatus.RUNNING
                    ).order_by(StrategyRun.started_at.desc()).first()
                    
                    if run:
                        # 尝试获取余额（如果交易所实例存在）
                        balance = None
                        if strategy.id in self.exchanges:
                            try:
                                balance = self.exchanges[strategy.id].get_balance()
                            except Exception as e:
                                logger.warning(f"获取策略 {strategy.id} 余额失败: {e}")
                        
                        run.status = StrategyStatus.STOPPED
                        run.current_balance = balance['total'] if balance else run.start_balance
                        run.stopped_at = datetime.utcnow()
                        logger.info(f"已更新策略 {strategy.id} 的运行记录状态")
            
            db.commit()
            logger.info(f"策略状态恢复完成，共恢复 {len(running_strategies)} 个策略")
            
        except Exception as e:
            logger.error(f"恢复策略状态失败: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


# 全局策略管理器实例
_strategy_manager: Optional[StrategyManager] = None


def get_strategy_manager() -> StrategyManager:
    """获取策略管理器单例"""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager

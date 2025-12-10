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
from .risk_manager import RiskManager
from .config import Config
from .strategies.base import BaseStrategy
from .strategies.martingale import MartingaleStrategy

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
        创建交易所实例
        
        Args:
            strategy_id: 策略ID
            use_testnet: 是否使用测试网
            
        Returns:
            交易所实例
        """
        if strategy_id in self.exchanges:
            return self.exchanges[strategy_id]
        
            # 从环境变量获取API密钥
        from dotenv import load_dotenv
        load_dotenv()
        
        if use_testnet:
            api_key = os.getenv('BINANCE_TESTNET_API_KEY') or os.getenv('BINANCE_API_KEY', '')
            api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY', '')
        else:
            api_key = os.getenv('BINANCE_API_KEY', '')
            api_secret = os.getenv('BINANCE_SECRET_KEY', '')
        
        exchange = BinanceExchange(api_key, api_secret, testnet=use_testnet)
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
            if 'martingale' in config_dict or 'trading' in config_dict:
                # 马丁格尔策略
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
            
            # 更新策略运行统计
            run = db.query(StrategyRun).filter(
                StrategyRun.strategy_id == strategy_id,
                StrategyRun.status == StrategyStatus.RUNNING
            ).order_by(StrategyRun.started_at.desc()).first()
            
            if run:
                run.total_trades += 1
                if trade_data.get('pnl', 0) > 0:
                    run.win_trades += 1
                elif trade_data.get('pnl', 0) < 0:
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
            run = StrategyRun(
                strategy_id=strategy_id,
                status=StrategyStatus.RUNNING,
                start_balance=balance['total'],
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
        if strategy_id not in self.strategies:
            logger.warning(f"策略未运行: {strategy_id}")
            return False
        
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
            
            # 更新数据库
            db = SessionLocal()
            try:
                strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
                if strategy:
                    strategy.status = StrategyStatus.STOPPED
                
                run = db.query(StrategyRun).filter(
                    StrategyRun.strategy_id == strategy_id,
                    StrategyRun.status == StrategyStatus.RUNNING
                ).order_by(StrategyRun.started_at.desc()).first()
                
                if run:
                    balance = self.exchanges[strategy_id].get_balance()
                    run.status = StrategyStatus.STOPPED
                    run.current_balance = balance['total']
                    run.stopped_at = datetime.utcnow()
                
                db.commit()
            finally:
                db.close()
            
            # 清理
            del self.strategies[strategy_id]
            if strategy_id in self.strategy_tasks:
                del self.strategy_tasks[strategy_id]
            
            logger.info(f"策略已停止: {strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止策略失败: {e}", exc_info=True)
            return False
    
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


# 全局策略管理器实例
_strategy_manager: Optional[StrategyManager] = None


def get_strategy_manager() -> StrategyManager:
    """获取策略管理器单例"""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager

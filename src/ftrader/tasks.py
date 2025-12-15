"""后台任务模块"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models.account import AccountSnapshot
from .models.position import Position
from .strategy_manager import get_strategy_manager

logger = logging.getLogger(__name__)


class BackgroundTasks:
    """后台任务管理器"""
    
    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动后台任务"""
        if self.is_running:
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._run_snapshots())
        logger.info("后台任务已启动")
    
    async def stop(self):
        """停止后台任务"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("后台任务已停止")
    
    async def _run_snapshots(self):
        """运行账户快照任务"""
        while self.is_running:
            try:
                await self._save_account_snapshot()
                await self._update_positions()  # 更新持仓信息
                await asyncio.sleep(60)  # 每分钟保存一次快照和更新持仓
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"后台任务执行失败: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _save_account_snapshot(self):
        """保存账户快照"""
        from .exchange_manager import get_exchange
        
        try:
            # 使用单例管理器获取exchange实例
            exchange = get_exchange()
        except Exception as e:
            logger.warning(f"获取交易所实例失败，无法保存快照: {e}")
            return
        
        # 获取余额
        try:
            balance = exchange.get_balance()
        except Exception as e:
            logger.warning(f"获取余额失败，无法保存快照: {e}")
            return
        
        # 检查余额是否为None
        if balance is None:
            logger.warning("余额为None，无法保存快照")
            return
        
        # 计算总盈亏（需要初始余额，这里简化处理）
        db = SessionLocal()
        try:
            # 获取最近的快照作为参考
            last_snapshot = db.query(AccountSnapshot).order_by(
                AccountSnapshot.snapshot_at.desc()
            ).first()
            
            total_pnl = None
            total_pnl_percent = None
            
            if last_snapshot and balance:
                total_pnl = balance['total'] - last_snapshot.total_balance
                if last_snapshot.total_balance > 0:
                    total_pnl_percent = (total_pnl / last_snapshot.total_balance) * 100
            
            if balance:
                snapshot = AccountSnapshot(
                    total_balance=balance['total'],
                    free_balance=balance['free'],
                    used_balance=balance['used'],
                    total_pnl=total_pnl,
                    total_pnl_percent=total_pnl_percent,
                    snapshot_at=datetime.utcnow()
                )
                
                db.add(snapshot)
                db.commit()
                logger.debug(f"账户快照已保存: balance={balance['total']:.2f} USDT")
            else:
                logger.warning("余额为None，跳过保存快照")
            
        except Exception as e:
            logger.error(f"保存账户快照失败: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    async def _update_positions(self):
        """更新持仓的当前价格和未实现盈亏"""
        from .exchange_manager import get_exchange
        
        try:
            # 使用单例管理器获取exchange实例
            exchange = get_exchange()
        except Exception as e:
            logger.warning(f"获取交易所实例失败，无法更新持仓: {e}")
            return
        
        if not exchange:
            return
        
        db = SessionLocal()
        try:
            # 获取所有未平仓的持仓
            positions = db.query(Position).filter(Position.is_closed == False).all()
            
            if not positions:
                logger.debug("没有未平仓的持仓，跳过更新")
                return
            
            logger.debug(f"开始更新 {len(positions)} 个持仓的价格和盈亏信息")
            
            # 一次性获取所有交易所持仓（优化性能）
            exchange_positions = exchange.get_all_open_positions()
            logger.debug(f"从交易所获取到 {len(exchange_positions)} 个持仓")
            
            for position in positions:
                try:
                    # 获取当前价格
                    ticker = exchange.get_ticker(position.symbol)
                    if ticker:
                        current_price = ticker.get('last')
                        if current_price:
                            position.current_price = current_price
                            
                            # 计算未实现盈亏
                            if position.side.value == 'long':
                                # 做多：盈亏 = (当前价格 - 开仓价格) * 合约数量
                                price_diff = current_price - position.entry_price
                                position.unrealized_pnl = price_diff * position.contracts
                            else:
                                # 做空：盈亏 = (开仓价格 - 当前价格) * 合约数量
                                price_diff = position.entry_price - current_price
                                position.unrealized_pnl = price_diff * position.contracts
                            
                            # 计算盈亏百分比
                            if position.entry_price > 0:
                                position.unrealized_pnl_percent = (price_diff / position.entry_price) * 100
                            
                            position.updated_at = datetime.utcnow()
                            logger.debug(f"已更新持仓 {position.id} ({position.symbol}): 当前价格={current_price:.2f}, 盈亏={position.unrealized_pnl:.2f}")
                    
                    # 检查交易所中是否还有实际持仓
                    exchange_position = exchange_positions.get(position.symbol)
                    if not exchange_position or exchange_position.get('contracts', 0) == 0:
                        # 交易所中没有持仓，可能已经平仓，标记为已平仓
                        logger.info(f"持仓 {position.id} ({position.symbol}) 在交易所中不存在或已平仓，标记为已平仓")
                        position.is_closed = True
                        position.closed_at = datetime.utcnow()
                    else:
                        # 如果交易所中有持仓，也可以使用交易所的盈亏数据（如果可用）
                        if exchange_position.get('unrealizedPnl') is not None:
                            position.unrealized_pnl = exchange_position.get('unrealizedPnl')
                        if exchange_position.get('percentage') is not None:
                            position.unrealized_pnl_percent = exchange_position.get('percentage')
                    
                except Exception as e:
                    logger.warning(f"更新持仓 {position.id} ({position.symbol}) 失败: {e}", exc_info=True)
                    continue
            
            db.commit()
            logger.info(f"已更新 {len(positions)} 个持仓的价格和盈亏信息")
                
        except Exception as e:
            logger.error(f"更新持仓信息失败: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


# 全局后台任务实例
_background_tasks: Optional[BackgroundTasks] = None


def get_background_tasks() -> BackgroundTasks:
    """获取后台任务管理器单例"""
    global _background_tasks
    if _background_tasks is None:
        _background_tasks = BackgroundTasks()
    return _background_tasks

"""策略管理API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models.strategy import Strategy, StrategyRun, StrategyStatus, StrategyType
from ..strategy_manager import get_strategy_manager
import yaml

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
async def stop_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """停止策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    if strategy.status != StrategyStatus.RUNNING:
        raise HTTPException(status_code=400, detail="策略未在运行")
    
    manager = get_strategy_manager()
    success = await manager.stop_strategy(strategy_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="停止策略失败")
    
    return {"message": "策略已停止"}


@router.get("/{strategy_id}/status")
async def get_strategy_status(strategy_id: int, db: Session = Depends(get_db)):
    """获取策略状态"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    manager = get_strategy_manager()
    status = manager.get_strategy_status(strategy_id)
    
    if not status:
        raise HTTPException(status_code=500, detail="获取策略状态失败")
    
    return status


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

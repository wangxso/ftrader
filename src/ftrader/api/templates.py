"""策略模板API"""

from fastapi import APIRouter
from typing import List, Dict, Any
from pydantic import BaseModel

from ..strategy_templates import get_all_templates, get_template

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateInfo(BaseModel):
    """模板信息"""
    id: str
    name: str
    description: str
    category: str


class TemplateDetail(BaseModel):
    """模板详情"""
    id: str
    name: str
    description: str
    category: str
    config_yaml: str


@router.get("", response_model=List[TemplateInfo])
async def get_templates():
    """获取所有策略模板列表"""
    templates = get_all_templates()
    return templates


@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template_detail(template_id: str):
    """获取策略模板详情"""
    template = get_template(template_id)
    if not template:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="模板不存在")
    
    return {
        'id': template.id,
        'name': template.name,
        'description': template.description,
        'category': template.category,
        'config_yaml': template.config_yaml,
    }

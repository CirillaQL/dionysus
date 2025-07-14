from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.internal.simpcity.simpcity import get_threads_list, get_thread_info, get_thread_posts, get_thread_info_by_id, get_thread_posts_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["threads"])

class ThreadInfo(BaseModel):
    """线程信息模型"""
    id: int
    thread_title: str
    thread_url: str
    thread_uuid: str
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    avatar_img: Optional[str] = None
    description: Optional[str] = None
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    posts_count: int
    latest_post_timestamp: Optional[str] = None
    first_post_timestamp: Optional[str] = None
    authors_count: int

class ThreadsListResponse(BaseModel):
    """线程列表响应模型"""
    success: bool
    message: str
    data: List[ThreadInfo]
    total_count: int

@router.get("/list", response_model=ThreadsListResponse)
async def list_threads(
    limit: int = 50,
    offset: int = 0,
    config_path: str = "config.yaml"
):
    """
    获取线程列表
    
    从PostgreSQL数据库中获取所有线程的信息
    
    Args:
        limit: 返回的线程数量限制，默认50
        offset: 偏移量，默认0
        config_path: 配置文件路径
        
    Returns:
        线程列表响应
    """
    try:
        logger.info(f"获取线程列表 - limit: {limit}, offset: {offset}")
        
        # 调用内部服务获取线程列表
        threads_data = get_threads_list(
            limit=limit,
            offset=offset,
            config_path=config_path
        )
        
        return ThreadsListResponse(
            success=True,
            message="获取线程列表成功",
            data=threads_data["threads"],
            total_count=threads_data["total_count"]
        )
        
    except Exception as e:
        logger.error(f"获取线程列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取线程列表失败: {str(e)}"
        )

@router.get("/id/{thread_id}", response_model=Dict[str, Any])
async def get_thread_by_id(
    thread_id: int,
    config_path: str = "config.yaml"
):
    """
    根据线程ID获取线程基本信息
    
    Args:
        thread_id: 线程的数据库自增ID
        config_path: 配置文件路径
        
    Returns:
        线程基本信息
    """
    try:
        logger.info(f"获取线程信息 - ID: {thread_id}")
        
        # 获取线程基本信息
        thread_info = get_thread_info_by_id(thread_id, config_path)
        if not thread_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到线程 ID: {thread_id}"
            )
        
        return {
            "success": True,
            "message": "获取线程信息成功",
            "data": thread_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取线程信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取线程信息失败: {str(e)}"
        )

@router.get("/id/{thread_id}/posts", response_model=Dict[str, Any])
async def get_thread_posts_by_id_endpoint(
    thread_id: int,
    limit: int = 50,
    offset: int = 0,
    config_path: str = "config.yaml"
):
    """
    根据线程ID获取帖子列表
    
    Args:
        thread_id: 线程的数据库自增ID
        limit: 返回的帖子数量限制，默认50
        offset: 偏移量，默认0
        config_path: 配置文件路径
        
    Returns:
        帖子列表响应
    """
    try:
        logger.info(f"获取线程帖子 - ID: {thread_id}, limit: {limit}, offset: {offset}")
        
        # 获取线程帖子列表
        posts_data = get_thread_posts_by_id(thread_id, limit, offset, config_path)
        
        if posts_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到线程 ID: {thread_id}"
            )
        
        return {
            "success": True,
            "message": "获取线程帖子成功",
            "data": posts_data["posts"],
            "total_count": posts_data["total_count"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取线程帖子失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取线程帖子失败: {str(e)}"
        )

@router.get("/{thread_url:path}", response_model=Dict[str, Any])
async def get_thread_detail(
    thread_url: str,
    limit: int = 50,
    offset: int = 0,
    config_path: str = "config.yaml"
):
    """
    获取指定线程的详细信息和帖子列表
    
    Args:
        thread_url: 线程URL
        limit: 返回的帖子数量限制，默认50
        offset: 偏移量，默认0
        config_path: 配置文件路径
        
    Returns:
        线程详细信息和帖子列表
    """
    try:
        logger.info(f"获取线程详细信息 - URL: {thread_url}")
        
        # 获取线程基本信息
        thread_info = get_thread_info(thread_url, config_path)
        if not thread_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到线程: {thread_url}"
            )
        
        # 获取线程帖子列表
        posts_data = get_thread_posts(thread_url, limit, offset, config_path)
        
        return {
            "success": True,
            "message": "获取线程详细信息成功",
            "thread_info": thread_info,
            "posts": posts_data["posts"],
            "total_posts": posts_data["total_count"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取线程详细信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取线程详细信息失败: {str(e)}"
        )

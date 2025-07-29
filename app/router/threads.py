from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import re
import json

from app.internal.simpcity.simpcity import get_threads_list, get_thread_info, get_thread_posts, get_thread_info_by_id, get_thread_posts_by_id
from crawler.download.bunkr import download_from_bunkr

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

class DownloadRequest(BaseModel):
    """下载请求模型"""
    thread_url: str
    post_id: str
    download_dir: Optional[str] = "downloads"
    ignore_patterns: Optional[List[str]] = None
    include_patterns: Optional[List[str]] = None

class DownloadResponse(BaseModel):
    """下载响应模型"""
    success: bool
    message: str
    post_id: str
    thread_url: str
    bunkr_links_found: int
    download_results: List[Dict[str, Any]]
    errors: List[str]

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

def get_post_by_id(post_id: str, thread_url: str, config_path: str = "config.yaml") -> Optional[Dict[str, Any]]:
    """
    根据post_id和thread_url获取特定帖子的详细信息
    
    Args:
        post_id: 帖子ID
        thread_url: 线程URL  
        config_path: 配置文件路径
    
    Returns:
        帖子信息字典或None
    """
    try:
        from db.postgre import PostgreSQLManager
        
        db_manager = PostgreSQLManager(config_path)
        
        # 查询特定帖子 - 使用新的表结构
        query = """
        SELECT r.id, r.uuid, r.thread_uuid, r.post_id, r.author_name, 
               r.author_id, r.author_profile_url, r.post_timestamp,
               r.content_text, r.content_html, r.image_urls, 
               r.external_links, r.iframe_urls, r.floor,
               r.create_time, r.update_time, r.is_deleted,
               t.url as thread_url,
               t.name as thread_name,
               react.reactions
        FROM simpcity_thread_response r
        JOIN simpcity_thread_metadata t ON r.thread_uuid = t.uuid
        LEFT JOIN simpcity_thread_reactions react ON r.uuid = react.post_uuid
        WHERE r.post_id = %s AND t.url = %s AND r.is_deleted = FALSE
        """
        
        result = db_manager.execute_one(query, (post_id, thread_url))
        
        if result:
            return {
                "id": result["id"],
                "uuid": str(result["uuid"]),
                "thread_uuid": str(result["thread_uuid"]),
                "post_id": result["post_id"],
                "author_name": result["author_name"],
                "author_id": result["author_id"],
                "author_profile_url": result["author_profile_url"],
                "post_timestamp": result["post_timestamp"],
                "content_text": result["content_text"],
                "content_html": result["content_html"],
                "image_urls": result["image_urls"] or [],
                "external_links": result["external_links"] or [],
                "iframe_urls": result["iframe_urls"] or [],
                "floor": result["floor"],
                "reactions": result["reactions"],
                "create_time": result["create_time"].isoformat() if result["create_time"] else None,
                "update_time": result["update_time"].isoformat() if result["update_time"] else None,
                "is_deleted": result["is_deleted"],
                "thread_url": result["thread_url"],
                "thread_name": result["thread_name"]
            }
        
        return None
        
    except Exception as e:
        logger.error(f"获取帖子 {post_id} 失败: {str(e)}")
        return None
    finally:
        if 'db_manager' in locals():
            db_manager.close_all_connections()

def extract_bunkr_links(external_links: List[str]) -> List[str]:
    """
    从外部链接列表中提取bunkr相关链接
    
    Args:
        external_links: 外部链接列表
    
    Returns:
        bunkr链接列表
    """
    bunkr_pattern = re.compile(r'bunkr\.\w+')
    bunkr_links = []
    
    for link in external_links:
        if bunkr_pattern.search(link):
            bunkr_links.append(link)
    
    return bunkr_links

@router.post("/download", response_model=DownloadResponse)
async def download_post_bunkr_links(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
):
    """
    下载指定帖子中的bunkr外部链接
    
    从数据库中获取指定的帖子，提取其外部链接中的bunkr链接并进行下载
    
    Args:
        request: 下载请求参数
        
    Returns:
        下载结果响应
    """
    try:
        logger.info(f"开始处理下载请求 - Post ID: {request.post_id}, Thread URL: {request.thread_url}")
        
        # 1. 获取帖子信息
        post_data = get_post_by_id(request.post_id, request.thread_url)
        if not post_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到帖子 ID: {request.post_id} 在线程: {request.thread_url}"
            )
        
        # 2. 提取外部链接
        external_links = post_data.get('external_links', [])
        if isinstance(external_links, str):
            try:
                external_links = json.loads(external_links)
            except json.JSONDecodeError:
                external_links = []
        
        # 3. 过滤出bunkr链接
        bunkr_links = extract_bunkr_links(external_links)
        
        if not bunkr_links:
            return DownloadResponse(
                success=True,
                message="该帖子中没有找到bunkr链接",
                post_id=request.post_id,
                thread_url=request.thread_url,
                bunkr_links_found=0,
                download_results=[],
                errors=[]
            )
        
        logger.info(f"找到 {len(bunkr_links)} 个bunkr链接: {bunkr_links}")
        
        # 4. 后台执行下载任务
        download_results = []
        errors = []
        
        def download_task():
            """后台下载任务"""
            try:
                for i, link in enumerate(bunkr_links):
                    logger.info(f"正在下载第 {i+1}/{len(bunkr_links)} 个链接: {link}")
                    try:
                        result = download_from_bunkr(
                            url=link,
                            download_dir=request.download_dir,
                            ignore_patterns=request.ignore_patterns,
                            include_patterns=request.include_patterns,
                            use_async=False
                        )
                        download_results.append({
                            "url": link,
                            "result": result
                        })
                        logger.info(f"链接 {link} 下载完成: {result}")
                    except Exception as e:
                        error_msg = f"下载链接 {link} 失败: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        download_results.append({
                            "url": link,
                            "result": {"success": False, "error": str(e)}
                        })
                        
            except Exception as e:
                logger.error(f"下载任务执行失败: {str(e)}")
                errors.append(f"下载任务执行失败: {str(e)}")
        
        # 添加后台任务
        background_tasks.add_task(download_task)
        
        return DownloadResponse(
            success=True,
            message=f"找到 {len(bunkr_links)} 个bunkr链接，下载任务已启动，正在后台执行",
            post_id=request.post_id,
            thread_url=request.thread_url,
            bunkr_links_found=len(bunkr_links),
            download_results=[],  # 后台任务，暂时返回空结果
            errors=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载请求处理失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载请求处理失败: {str(e)}"
        )

@router.post("/download-sync", response_model=DownloadResponse)
async def download_post_bunkr_links_sync(request: DownloadRequest):
    """
    同步下载指定帖子中的bunkr外部链接
    
    与 /download 接口不同，此接口会等待所有下载任务完成后返回结果
    
    Args:
        request: 下载请求参数
        
    Returns:
        包含完整下载结果的响应
    """
    try:
        logger.info(f"开始处理同步下载请求 - Post ID: {request.post_id}, Thread URL: {request.thread_url}")
        
        # 1. 获取帖子信息
        post_data = get_post_by_id(request.post_id, request.thread_url)
        if not post_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到帖子 ID: {request.post_id} 在线程: {request.thread_url}"
            )
        
        # 2. 提取外部链接
        external_links = post_data.get('external_links', [])
        if isinstance(external_links, str):
            try:
                external_links = json.loads(external_links)
            except json.JSONDecodeError:
                external_links = []
        
        # 3. 过滤出bunkr链接
        bunkr_links = extract_bunkr_links(external_links)
        
        if not bunkr_links:
            return DownloadResponse(
                success=True,
                message="该帖子中没有找到bunkr链接",
                post_id=request.post_id,
                thread_url=request.thread_url,
                bunkr_links_found=0,
                download_results=[],
                errors=[]
            )
        
        logger.info(f"找到 {len(bunkr_links)} 个bunkr链接: {bunkr_links}")
        
        # 4. 同步执行下载任务
        download_results = []
        errors = []
        
        for i, link in enumerate(bunkr_links):
            logger.info(f"正在下载第 {i+1}/{len(bunkr_links)} 个链接: {link}")
            try:
                result = download_from_bunkr(
                    url=link,
                    download_dir=request.download_dir,
                    ignore_patterns=request.ignore_patterns,
                    include_patterns=request.include_patterns,
                    use_async=False
                )
                download_results.append({
                    "url": link,
                    "result": result
                })
                logger.info(f"链接 {link} 下载完成: {result}")
            except Exception as e:
                error_msg = f"下载链接 {link} 失败: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                download_results.append({
                    "url": link,
                    "result": {"success": False, "error": str(e)}
                })
        
        # 统计成功的下载数量
        successful_downloads = sum(1 for result in download_results if result.get("result", {}).get("success", False))
        
        return DownloadResponse(
            success=len(errors) == 0,
            message=f"下载完成。成功: {successful_downloads}/{len(bunkr_links)}，失败: {len(errors)}",
            post_id=request.post_id,
            thread_url=request.thread_url,
            bunkr_links_found=len(bunkr_links),
            download_results=download_results,
            errors=errors
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步下载请求处理失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步下载请求处理失败: {str(e)}"
        )

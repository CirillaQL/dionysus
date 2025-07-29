# Copyright 2025 SimpCity API Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, List
import logging
import asyncio
from datetime import datetime
import uuid
from pathlib import Path
import os

from crawler.simpcity.simpcity import crawler, sync, watch
from config.config import get_config
from cookies.cookies import BrowserCookies
from app.router.threads import router as threads_router

# 配置统一日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SimpCity API",
    description="SimpCity论坛爬虫API接口",
    version="1.0.0"
)

# 注册路由
app.include_router(threads_router)

# 配置静态文件服务
dist_path = Path("dist")
if dist_path.exists():
    # 挂载静态文件
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
    
    # 提供前端页面
    @app.get("/")
    async def serve_frontend():
        """提供前端页面"""
        return FileResponse("dist/index.html")
    
    # 处理前端路由（SPA 路由）
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """处理前端 SPA 路由"""
        # 如果是 API 路由，跳过
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # 检查是否是静态文件
        static_file_path = dist_path / path
        if static_file_path.exists() and static_file_path.is_file():
            return FileResponse(static_file_path)
        
        # 否则返回 index.html（SPA 路由）
        return FileResponse("dist/index.html")

# 全局监控器存储
active_watchers: Dict[str, Dict[str, Any]] = {}

# Pydantic模型定义
class CrawlerRequest(BaseModel):
    thread_url: HttpUrl = Field(..., description="帖子URL")
    thread_title: Optional[str] = Field(None, description="帖子标题")
    enable_reactions: bool = Field(True, description="是否启用reactions抓取")
    save_to_db: bool = Field(True, description="是否保存到数据库")
    config_path: str = Field("config.yaml", description="配置文件路径")

class SyncRequest(BaseModel):
    thread_url: HttpUrl = Field(..., description="帖子URL")
    thread_title: Optional[str] = Field(None, description="帖子标题")
    enable_reactions: bool = Field(True, description="是否启用reactions抓取")
    save_to_db: bool = Field(True, description="是否保存到数据库")
    config_path: str = Field("config.yaml", description="配置文件路径")

class WatchRequest(BaseModel):
    thread_url: HttpUrl = Field(..., description="帖子URL")
    thread_title: Optional[str] = Field(None, description="帖子标题")
    schedule_type: str = Field("interval", description="调度类型: interval 或 cron")
    interval_minutes: int = Field(60, description="间隔时间（分钟），仅当schedule_type为interval时有效")
    cron_expression: Optional[str] = Field(None, description="cron表达式，仅当schedule_type为cron时有效")
    enable_reactions: bool = Field(True, description="是否启用reactions抓取")
    save_to_db: bool = Field(True, description="是否保存到数据库")
    config_path: str = Field("config.yaml", description="配置文件路径")

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# 辅助函数
def load_cookies_from_config(config_path: str = "config.yaml") -> Dict[str, str]:
    """从配置文件或浏览器cookies文件加载cookies"""
    try:
        # 首先尝试从配置文件读取
        config = get_config(config_path)
        browser_cookies = config.get("cookies")
        
        cookies_manager = BrowserCookies()
        
        if browser_cookies:
            logger.info("从配置文件加载cookies...")
            cookies_manager.add_cookies_from_dict(browser_cookies)
        else:
            logger.info("配置文件中未找到cookies，尝试从浏览器cookies文件加载...")
        
        requests_cookies = cookies_manager.to_requests_cookies("simpcity.su")
        
        if not requests_cookies:
            raise ValueError("未找到任何有效的cookies")
        
        logger.info(f"成功加载 {len(requests_cookies)} 个cookies")
        return requests_cookies
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置文件config.yaml不存在，请复制config.yaml.example为config.yaml并填写配置"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"加载cookies失败: {str(e)}"
        )

@app.get("/api", response_model=ApiResponse)
async def api_root():
    """API根路径，返回API信息"""
    return ApiResponse(
        success=True,
        message="SimpCity API服务运行正常",
        data={
            "version": "1.0.0",
            "endpoints": [
                "/api/docs - API文档",
                "/api/threads - 获取线程列表",
                "/api/threads/{thread_url} - 获取线程详情",
                "/api/threads/download - 下载帖子bunkr链接（后台任务）",
                "/api/threads/download-sync - 同步下载帖子bunkr链接",
                "/api/crawler - 爬取帖子",
                "/api/sync - 同步帖子",
                "/api/watch - 监控帖子",
                "/api/watchers - 获取所有监控器",
                "/api/watchers/{watcher_id} - 管理监控器"
            ]
        }
    )

@app.post("/api/crawler", response_model=ApiResponse)
async def crawl_thread(request: CrawlerRequest, background_tasks: BackgroundTasks):
    """
    爬取帖子
    
    完整爬取指定帖子的所有页面和帖子数据
    """
    request_id = str(uuid.uuid4())
    
    try:
        logger.info(f"[{request_id}] 开始爬取帖子: {request.thread_url}")
        
        # 加载cookies
        cookies = load_cookies_from_config(request.config_path)
        
        # 执行爬取（在后台任务中执行以避免阻塞）
        def run_crawler():
            try:
                result = crawler(
                    thread_url=str(request.thread_url),
                    cookies=cookies,
                    thread_title=request.thread_title,
                    enable_reactions=request.enable_reactions,
                    save_to_db=request.save_to_db,
                    config_path=request.config_path
                )
                logger.info(f"[{request_id}] 爬取完成: {result}")
            except Exception as e:
                logger.error(f"[{request_id}] 爬取失败: {str(e)}")
        
        background_tasks.add_task(run_crawler)
        
        return ApiResponse(
            success=True,
            message="爬取任务已启动，正在后台执行",
            data={
                "thread_url": str(request.thread_url),
                "thread_title": request.thread_title,
                "enable_reactions": request.enable_reactions,
                "save_to_db": request.save_to_db
            },
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] 爬取任务启动失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"爬取任务启动失败: {str(e)}"
        )

@app.post("/api/sync", response_model=ApiResponse)
async def sync_thread(request: SyncRequest):
    """
    同步帖子
    
    对比现有数据和最新数据，进行增量同步
    """
    request_id = str(uuid.uuid4())
    
    try:
        logger.info(f"[{request_id}] 开始同步帖子: {request.thread_url}")
        
        # 加载cookies
        cookies = load_cookies_from_config(request.config_path)
        
        # 执行同步
        result = sync(
            thread_url=str(request.thread_url),
            cookies=cookies,
            thread_title=request.thread_title,
            enable_reactions=request.enable_reactions,
            save_to_db=request.save_to_db,
            config_path=request.config_path
        )
        
        logger.info(f"[{request_id}] 同步完成: {result}")
        
        if result['success']:
            return ApiResponse(
                success=True,
                message="同步完成",
                data=result,
                request_id=request_id
            )
        else:
            return ApiResponse(
                success=False,
                message=f"同步失败: {result.get('error', '未知错误')}",
                data=result,
                request_id=request_id
            )
        
    except Exception as e:
        logger.error(f"[{request_id}] 同步失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步失败: {str(e)}"
        )

@app.post("/api/watch", response_model=ApiResponse)
async def start_watch(request: WatchRequest):
    """
    启动监控
    
    创建定时任务监控指定帖子的更新
    """
    request_id = str(uuid.uuid4())
    watcher_id = str(uuid.uuid4())
    
    try:
        logger.info(f"[{request_id}] 开始创建监控器: {request.thread_url}")
        
        # 加载cookies
        cookies = load_cookies_from_config(request.config_path)
        
        # 创建监控器
        watcher = watch(
            thread_url=str(request.thread_url),
            cookies=cookies,
            schedule_type=request.schedule_type,
            interval_minutes=request.interval_minutes,
            cron_expression=request.cron_expression,
            thread_title=request.thread_title,
            enable_reactions=request.enable_reactions,
            save_to_db=request.save_to_db,
            config_path=request.config_path
        )
        
        # 启动监控
        watcher['start']()
        
        # 保存到全局存储
        active_watchers[watcher_id] = {
            'watcher': watcher,
            'request': request.dict(),
            'created_at': datetime.now(),
            'request_id': request_id
        }
        
        # 获取状态
        status_info = watcher['status']()
        
        logger.info(f"[{request_id}] 监控器已启动: {watcher_id}")
        
        return ApiResponse(
            success=True,
            message="监控已启动",
            data={
                "watcher_id": watcher_id,
                "status": status_info,
                "created_at": datetime.now()
            },
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] 监控器启动失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"监控器启动失败: {str(e)}"
        )

@app.get("/api/watchers", response_model=ApiResponse)
async def list_watchers():
    """
    获取所有监控器列表
    """
    try:
        watchers_info = []
        
        for watcher_id, watcher_data in active_watchers.items():
            watcher = watcher_data['watcher']
            status_info = watcher['status']()
            
            watchers_info.append({
                "watcher_id": watcher_id,
                "thread_url": status_info['thread_url'],
                "thread_title": status_info['thread_title'],
                "is_running": status_info['is_running'],
                "schedule_type": status_info['schedule_type'],
                "interval_minutes": status_info['interval_minutes'],
                "cron_expression": status_info['cron_expression'],
                "sync_count": status_info['sync_count'],
                "error_count": status_info['error_count'],
                "last_sync_time": status_info['last_sync_time'],
                "next_run_time": status_info['next_run_time'],
                "created_at": watcher_data['created_at']
            })
        
        return ApiResponse(
            success=True,
            message=f"当前有 {len(watchers_info)} 个监控器",
            data={"watchers": watchers_info}
        )
        
    except Exception as e:
        logger.error(f"获取监控器列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取监控器列表失败: {str(e)}"
        )

@app.get("/api/watchers/{watcher_id}", response_model=ApiResponse)
async def get_watcher(watcher_id: str):
    """
    获取指定监控器的详细状态
    """
    try:
        if watcher_id not in active_watchers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"监控器 {watcher_id} 不存在"
            )
        
        watcher_data = active_watchers[watcher_id]
        watcher = watcher_data['watcher']
        status_info = watcher['status']()
        
        return ApiResponse(
            success=True,
            message="监控器状态获取成功",
            data={
                "watcher_id": watcher_id,
                "status": status_info,
                "request": watcher_data['request'],
                "created_at": watcher_data['created_at']
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取监控器状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取监控器状态失败: {str(e)}"
        )

@app.delete("/api/watchers/{watcher_id}", response_model=ApiResponse)
async def stop_watcher(watcher_id: str):
    """
    停止并删除指定监控器
    """
    try:
        if watcher_id not in active_watchers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"监控器 {watcher_id} 不存在"
            )
        
        watcher_data = active_watchers[watcher_id]
        watcher = watcher_data['watcher']
        
        # 停止监控
        watcher['stop']()
        
        # 从存储中删除
        del active_watchers[watcher_id]
        
        logger.info(f"监控器 {watcher_id} 已停止并删除")
        
        return ApiResponse(
            success=True,
            message="监控器已停止并删除",
            data={"watcher_id": watcher_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止监控器失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止监控器失败: {str(e)}"
        )

@app.post("/api/watchers/{watcher_id}/force-sync", response_model=ApiResponse)
async def force_sync_watcher(watcher_id: str):
    """
    手动触发指定监控器执行同步
    """
    try:
        if watcher_id not in active_watchers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"监控器 {watcher_id} 不存在"
            )
        
        watcher_data = active_watchers[watcher_id]
        watcher = watcher_data['watcher']
        
        # 手动触发同步
        watcher['force_sync']()
        
        logger.info(f"监控器 {watcher_id} 手动同步已触发")
        
        # 获取最新状态
        status_info = watcher['status']()
        
        return ApiResponse(
            success=True,
            message="手动同步已触发",
            data={
                "watcher_id": watcher_id,
                "status": status_info
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手动触发同步失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"手动触发同步失败: {str(e)}"
        )
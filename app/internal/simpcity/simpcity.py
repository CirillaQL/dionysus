from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from db.postgre import PostgreSQLManager

logger = logging.getLogger(__name__)

def get_threads_list(
    limit: int = 50,
    offset: int = 0,
    config_path: str = "config.yaml"
) -> Dict[str, Any]:
    """
    从PostgreSQL数据库中获取线程列表
    
    Args:
        limit: 返回的线程数量限制
        offset: 偏移量
        config_path: 配置文件路径
        
    Returns:
        包含线程列表和总数的字典
    """
    try:
        db_manager = PostgreSQLManager(config_path)
        
        # 获取线程统计信息的SQL查询
        threads_query = """
            SELECT 
                thread as thread_title,
                thread_url,
                COUNT(*) as posts_count,
                MAX(post_timestamp) as latest_post_timestamp,
                MIN(post_timestamp) as first_post_timestamp,
                COUNT(DISTINCT author_id) as authors_count
            FROM simpcity 
            WHERE thread IS NOT NULL 
                AND thread != ''
                AND (is_deleted IS NULL OR is_deleted = FALSE)
            GROUP BY thread, thread_url
            ORDER BY MAX(post_timestamp) DESC
            LIMIT %s OFFSET %s
        """
        
        # 获取总线程数的SQL查询
        count_query = """
            SELECT COUNT(DISTINCT thread_url) as total_count
            FROM simpcity 
            WHERE thread IS NOT NULL 
                AND thread != ''
                AND (is_deleted IS NULL OR is_deleted = FALSE)
        """
        
        # 执行查询
        threads_result = db_manager.execute_query(threads_query, (limit, offset))
        count_result = db_manager.execute_one(count_query)
        
        # 格式化结果
        threads_list = []
        for thread in threads_result:
            thread_info = {
                "thread_title": thread["thread_title"],
                "thread_url": thread["thread_url"],
                "posts_count": thread["posts_count"],
                "latest_post_timestamp": thread["latest_post_timestamp"],
                "first_post_timestamp": thread["first_post_timestamp"],
                "authors_count": thread["authors_count"]
            }
            threads_list.append(thread_info)
        
        total_count = count_result["total_count"] if count_result else 0
        
        logger.info(f"获取线程列表成功 - 返回 {len(threads_list)} 个线程，总数: {total_count}")
        
        return {
            "threads": threads_list,
            "total_count": total_count
        }
        
    except Exception as e:
        logger.error(f"获取线程列表失败: {str(e)}")
        raise e
    finally:
        if 'db_manager' in locals():
            db_manager.close_all_connections()

def get_thread_posts(
    thread_url: str,
    limit: int = 50,
    offset: int = 0,
    config_path: str = "config.yaml"
) -> Dict[str, Any]:
    """
    获取指定线程的帖子列表
    
    Args:
        thread_url: 线程URL
        limit: 返回的帖子数量限制
        offset: 偏移量
        config_path: 配置文件路径
        
    Returns:
        包含帖子列表和总数的字典
    """
    try:
        db_manager = PostgreSQLManager(config_path)
        
        # 获取帖子列表的SQL查询
        posts_query = """
            SELECT *
            FROM simpcity 
            WHERE thread_url = %s
                AND (is_deleted IS NULL OR is_deleted = FALSE)
            ORDER BY floor ASC
            LIMIT %s OFFSET %s
        """
        
        # 获取总帖子数的SQL查询
        count_query = """
            SELECT COUNT(*) as total_count
            FROM simpcity 
            WHERE thread_url = %s
                AND (is_deleted IS NULL OR is_deleted = FALSE)
        """
        
        # 执行查询
        posts_result = db_manager.execute_query(posts_query, (thread_url, limit, offset))
        count_result = db_manager.execute_one(count_query, (thread_url,))
        
        total_count = count_result["total_count"] if count_result else 0
        
        logger.info(f"获取线程 {thread_url} 的帖子列表成功 - 返回 {len(posts_result)} 个帖子，总数: {total_count}")
        
        return {
            "posts": posts_result,
            "total_count": total_count
        }
        
    except Exception as e:
        logger.error(f"获取线程帖子列表失败: {str(e)}")
        raise e
    finally:
        if 'db_manager' in locals():
            db_manager.close_all_connections()

def get_thread_info(
    thread_url: str,
    config_path: str = "config.yaml"
) -> Optional[Dict[str, Any]]:
    """
    获取指定线程的基本信息
    
    Args:
        thread_url: 线程URL
        config_path: 配置文件路径
        
    Returns:
        线程信息字典或None
    """
    try:
        db_manager = PostgreSQLManager(config_path)
        
        # 获取线程信息的SQL查询
        thread_info_query = """
            SELECT 
                thread as thread_title,
                thread_url,
                COUNT(*) as posts_count,
                MAX(post_timestamp) as latest_post_timestamp,
                MIN(post_timestamp) as first_post_timestamp,
                COUNT(DISTINCT author_id) as authors_count
            FROM simpcity 
            WHERE thread_url = %s
                AND (is_deleted IS NULL OR is_deleted = FALSE)
            GROUP BY thread, thread_url
        """
        
        # 执行查询
        result = db_manager.execute_one(thread_info_query, (thread_url,))
        
        if result:
            logger.info(f"获取线程 {thread_url} 的信息成功")
            return {
                "thread_title": result["thread_title"],
                "thread_url": result["thread_url"],
                "posts_count": result["posts_count"],
                "latest_post_timestamp": result["latest_post_timestamp"],
                "first_post_timestamp": result["first_post_timestamp"],
                "authors_count": result["authors_count"]
            }
        else:
            logger.warning(f"未找到线程 {thread_url}")
            return None
            
    except Exception as e:
        logger.error(f"获取线程信息失败: {str(e)}")
        raise e
    finally:
        if 'db_manager' in locals():
            db_manager.close_all_connections()

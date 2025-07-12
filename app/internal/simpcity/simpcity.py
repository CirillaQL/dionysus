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
    从PostgreSQL数据库中获取线程列表 - 适配新的三表结构
    
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
                tm.id,
                tm.name as thread_title,
                tm.url as thread_url,
                tm.uuid as thread_uuid,
                tm.categories,
                tm.tags,
                tm.avatar_img,
                tm.description,
                tm.create_time,
                tm.update_time,
                COUNT(tr.id) as posts_count,
                MAX(tr.post_timestamp) as latest_post_timestamp,
                MIN(tr.post_timestamp) as first_post_timestamp,
                COUNT(DISTINCT tr.author_id) as authors_count
            FROM simpcity_thread_metadata tm
            LEFT JOIN simpcity_thread_response tr ON tm.uuid = tr.thread_uuid 
                AND tr.is_deleted = false
            WHERE tm.is_deleted = false
            GROUP BY tm.id, tm.uuid, tm.name, tm.url, tm.categories, tm.tags, tm.avatar_img, tm.description, tm.create_time, tm.update_time
            ORDER BY MAX(tr.post_timestamp) DESC NULLS LAST
            LIMIT %s OFFSET %s
        """
        
        # 获取总线程数的SQL查询
        count_query = """
            SELECT COUNT(*) as total_count
            FROM simpcity_thread_metadata 
            WHERE is_deleted = false
        """
        
        # 执行查询
        threads_result = db_manager.execute_query(threads_query, (limit, offset))
        count_result = db_manager.execute_one(count_query)
        
        # 格式化结果
        threads_list = []
        for thread in threads_result:
            thread_info = {
                "id": thread["id"],
                "thread_title": thread["thread_title"],
                "thread_url": thread["thread_url"],
                "thread_uuid": str(thread["thread_uuid"]),
                "categories": thread["categories"],
                "tags": thread["tags"],
                "avatar_img": thread["avatar_img"],
                "description": thread["description"],
                "create_time": thread["create_time"].isoformat() if thread["create_time"] else None,
                "update_time": thread["update_time"].isoformat() if thread["update_time"] else None,
                "posts_count": thread["posts_count"] or 0,
                "latest_post_timestamp": str(thread["latest_post_timestamp"]) if thread["latest_post_timestamp"] else None,
                "first_post_timestamp": str(thread["first_post_timestamp"]) if thread["first_post_timestamp"] else None,
                "authors_count": thread["authors_count"] or 0
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
    获取指定线程的帖子列表 - 适配新的三表结构
    
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
        
        # 获取帖子列表的SQL查询（包含反应数据）
        posts_query = """
            SELECT 
                tr.*,
                trc.reactions
            FROM simpcity_thread_response tr
            JOIN simpcity_thread_metadata tm ON tr.thread_uuid = tm.uuid
            LEFT JOIN simpcity_thread_reactions trc ON tr.uuid = trc.post_uuid
            WHERE tm.url = %s
                AND tr.is_deleted = false
                AND tm.is_deleted = false
            ORDER BY tr.floor ASC
            LIMIT %s OFFSET %s
        """
        
        # 获取总帖子数的SQL查询
        count_query = """
            SELECT COUNT(*) as total_count
            FROM simpcity_thread_response tr
            JOIN simpcity_thread_metadata tm ON tr.thread_uuid = tm.uuid
            WHERE tm.url = %s
                AND tr.is_deleted = false
                AND tm.is_deleted = false
        """
        
        # 执行查询
        posts_result = db_manager.execute_query(posts_query, (thread_url, limit, offset))
        count_result = db_manager.execute_one(count_query, (thread_url,))
        
        # 格式化帖子数据
        formatted_posts = []
        for post in posts_result:
            formatted_post = {
                "id": post["id"],
                "uuid": str(post["uuid"]),
                "thread_uuid": str(post["thread_uuid"]),
                "post_id": post["post_id"],
                "author_name": post["author_name"],
                "author_id": post["author_id"],
                "author_profile_url": post["author_profile_url"],
                "post_timestamp": post["post_timestamp"],
                "content_text": post["content_text"],
                "content_html": post["content_html"],
                "image_urls": post["image_urls"] or [],
                "external_links": post["external_links"] or [],
                "iframe_urls": post["iframe_urls"] or [],
                "floor": post["floor"],
                "reactions": post["reactions"],
                "create_time": post["create_time"].isoformat() if post["create_time"] else None,
                "update_time": post["update_time"].isoformat() if post["update_time"] else None,
                "is_deleted": post["is_deleted"]
            }
            formatted_posts.append(formatted_post)
        
        total_count = count_result["total_count"] if count_result else 0
        
        logger.info(f"获取线程 {thread_url} 的帖子列表成功 - 返回 {len(formatted_posts)} 个帖子，总数: {total_count}")
        
        return {
            "posts": formatted_posts,
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
    获取指定线程的基本信息 - 适配新的三表结构
    
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
                tm.name as thread_title,
                tm.url as thread_url,
                tm.uuid as thread_uuid,
                tm.categories,
                tm.tags,
                tm.avatar_img,
                tm.description,
                tm.create_time,
                tm.update_time,
                COUNT(tr.id) as posts_count,
                MAX(tr.post_timestamp) as latest_post_timestamp,
                MIN(tr.post_timestamp) as first_post_timestamp,
                COUNT(DISTINCT tr.author_id) as authors_count
            FROM simpcity_thread_metadata tm
            LEFT JOIN simpcity_thread_response tr ON tm.uuid = tr.thread_uuid 
                AND tr.is_deleted = false
            WHERE tm.url = %s
                AND tm.is_deleted = false
            GROUP BY tm.uuid, tm.name, tm.url, tm.categories, tm.tags, tm.avatar_img, tm.description, tm.create_time, tm.update_time
        """
        
        # 执行查询
        result = db_manager.execute_one(thread_info_query, (thread_url,))
        
        if result:
            logger.info(f"获取线程 {thread_url} 的信息成功")
            return {
                "thread_title": result["thread_title"],
                "thread_url": result["thread_url"],
                "thread_uuid": str(result["thread_uuid"]),
                "categories": result["categories"],
                "tags": result["tags"],
                "avatar_img": result["avatar_img"],
                "description": result["description"],
                "create_time": result["create_time"].isoformat() if result["create_time"] else None,
                "update_time": result["update_time"].isoformat() if result["update_time"] else None,
                "posts_count": result["posts_count"] or 0,
                "latest_post_timestamp": str(result["latest_post_timestamp"]) if result["latest_post_timestamp"] else None,
                "first_post_timestamp": str(result["first_post_timestamp"]) if result["first_post_timestamp"] else None,
                "authors_count": result["authors_count"] or 0
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

def get_thread_info_by_id(
    thread_id: int,
    config_path: str = "config.yaml"
) -> Optional[Dict[str, Any]]:
    """
    根据线程ID获取线程基本信息 - 使用数据库自增ID
    
    Args:
        thread_id: 线程的数据库自增ID
        config_path: 配置文件路径
        
    Returns:
        线程信息字典或None
    """
    try:
        db_manager = PostgreSQLManager(config_path)
        
        # 获取线程信息的SQL查询 - 使用ID而不是URL
        thread_info_query = """
            SELECT 
                tm.id,
                tm.name as thread_title,
                tm.url as thread_url,
                tm.uuid as thread_uuid,
                tm.categories,
                tm.tags,
                tm.avatar_img,
                tm.description,
                tm.create_time,
                tm.update_time,
                COUNT(tr.id) as posts_count,
                MAX(tr.post_timestamp) as latest_post_timestamp,
                MIN(tr.post_timestamp) as first_post_timestamp,
                COUNT(DISTINCT tr.author_id) as authors_count
            FROM simpcity_thread_metadata tm
            LEFT JOIN simpcity_thread_response tr ON tm.uuid = tr.thread_uuid 
                AND tr.is_deleted = false
            WHERE tm.id = %s
                AND tm.is_deleted = false
            GROUP BY tm.id, tm.uuid, tm.name, tm.url, tm.categories, tm.tags, tm.avatar_img, tm.description, tm.create_time, tm.update_time
        """
        
        # 执行查询
        result = db_manager.execute_one(thread_info_query, (thread_id,))
        
        if result:
            logger.info(f"获取线程 ID {thread_id} 的信息成功")
            return {
                "id": result["id"],
                "thread_title": result["thread_title"],
                "thread_url": result["thread_url"],
                "thread_uuid": str(result["thread_uuid"]),
                "categories": result["categories"],
                "tags": result["tags"],
                "avatar_img": result["avatar_img"],
                "description": result["description"],
                "create_time": result["create_time"].isoformat() if result["create_time"] else None,
                "update_time": result["update_time"].isoformat() if result["update_time"] else None,
                "posts_count": result["posts_count"] or 0,
                "latest_post_timestamp": str(result["latest_post_timestamp"]) if result["latest_post_timestamp"] else None,
                "first_post_timestamp": str(result["first_post_timestamp"]) if result["first_post_timestamp"] else None,
                "authors_count": result["authors_count"] or 0
            }
        else:
            logger.warning(f"未找到线程 ID {thread_id}")
            return None
            
    except Exception as e:
        logger.error(f"获取线程信息失败: {str(e)}")
        raise e
    finally:
        if 'db_manager' in locals():
            db_manager.close_all_connections()

def get_thread_posts_by_id(
    thread_id: int,
    limit: int = 50,
    offset: int = 0,
    config_path: str = "config.yaml"
) -> Optional[Dict[str, Any]]:
    """
    根据线程ID获取帖子列表 - 使用数据库自增ID
    
    Args:
        thread_id: 线程的数据库自增ID
        limit: 返回的帖子数量限制
        offset: 偏移量
        config_path: 配置文件路径
        
    Returns:
        包含帖子列表和总数的字典，如果线程不存在则返回None
    """
    try:
        db_manager = PostgreSQLManager(config_path)
        
        # 首先验证线程是否存在
        thread_check_query = """
            SELECT id FROM simpcity_thread_metadata 
            WHERE id = %s AND is_deleted = false
        """
        thread_exists = db_manager.execute_one(thread_check_query, (thread_id,))
        
        if not thread_exists:
            logger.warning(f"线程 ID {thread_id} 不存在")
            return None
        
        # 获取帖子列表的SQL查询（包含反应数据）- 使用ID而不是URL
        posts_query = """
            SELECT 
                tr.*,
                trc.reactions
            FROM simpcity_thread_response tr
            JOIN simpcity_thread_metadata tm ON tr.thread_uuid = tm.uuid
            LEFT JOIN simpcity_thread_reactions trc ON tr.uuid = trc.post_uuid
            WHERE tm.id = %s
                AND tr.is_deleted = false
                AND tm.is_deleted = false
            ORDER BY tr.floor ASC
            LIMIT %s OFFSET %s
        """
        
        # 获取总帖子数的SQL查询
        count_query = """
            SELECT COUNT(*) as total_count
            FROM simpcity_thread_response tr
            JOIN simpcity_thread_metadata tm ON tr.thread_uuid = tm.uuid
            WHERE tm.id = %s
                AND tr.is_deleted = false
                AND tm.is_deleted = false
        """
        
        # 执行查询
        posts_result = db_manager.execute_query(posts_query, (thread_id, limit, offset))
        count_result = db_manager.execute_one(count_query, (thread_id,))
        
        # 格式化帖子数据
        formatted_posts = []
        for post in posts_result:
            formatted_post = {
                "id": post["id"],
                "uuid": str(post["uuid"]),
                "thread_uuid": str(post["thread_uuid"]),
                "post_id": post["post_id"],
                "author_name": post["author_name"],
                "author_id": post["author_id"],
                "author_profile_url": post["author_profile_url"],
                "post_timestamp": post["post_timestamp"],
                "content_text": post["content_text"],
                "content_html": post["content_html"],
                "image_urls": post["image_urls"] or [],
                "external_links": post["external_links"] or [],
                "iframe_urls": post["iframe_urls"] or [],
                "floor": post["floor"],
                "reactions": post["reactions"],
                "create_time": post["create_time"].isoformat() if post["create_time"] else None,
                "update_time": post["update_time"].isoformat() if post["update_time"] else None,
                "is_deleted": post["is_deleted"]
            }
            formatted_posts.append(formatted_post)
        
        total_count = count_result["total_count"] if count_result else 0
        
        logger.info(f"获取线程 ID {thread_id} 的帖子列表成功 - 返回 {len(formatted_posts)} 个帖子，总数: {total_count}")
        
        return {
            "posts": formatted_posts,
            "total_count": total_count
        }
        
    except Exception as e:
        logger.error(f"获取线程帖子列表失败: {str(e)}")
        raise e
    finally:
        if 'db_manager' in locals():
            db_manager.close_all_connections()

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

import requests
from bs4 import BeautifulSoup, Tag
import time
import random
import json
import threading
import logging
from datetime import datetime
import uuid
import copy

from urllib.parse import urljoin
from typing import Dict, Any, Optional, List, Union

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from db.postgre import PostgreSQLManager


def scrape_post_reactions(post_id: int, base_url: str, session: Optional[requests.Session] = None) -> int:
    """
    抓取单个帖子的reactions总数
    
    Args:
        post_id: 帖子ID
        base_url: 基础URL
        session: requests Session对象（可选）
    
    Returns:
        reactions总数
    """
    if session is None:
        session = requests.Session()
    
    reactions_url = urljoin(base_url, f'posts/{post_id}/reactions')
    
    try:
        response = session.get(reactions_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找"All"标签页，获取总反应数
        all_tab = soup.select_one('h3.tabs a.tabs-tab.is-active')
        if all_tab:
            tab_text = all_tab.get_text(strip=True)
            # 解析 "All (287)" 格式
            if '(' in tab_text and ')' in tab_text:
                count_str = tab_text.split('(')[1].split(')')[0].strip()
                try:
                    return int(count_str)
                except ValueError:
                    pass
        
        return 0
        
    except Exception as e:
        print(f"获取帖子 {post_id} 的reactions失败: {e}")
        return 0


def parse_post_enhanced(post_tag: Tag, base_url: str, session: Optional[requests.Session] = None, enable_reactions: bool = True) -> Dict[str, Any]:
    """
    解析单个帖子的HTML，提取更丰富的信息，包括用户详情、多媒体内容等。
    
    Args:
        post_tag: 帖子的HTML Tag对象
        base_url: 基础URL
        session: requests Session对象（可选）
        enable_reactions: 是否启用reactions抓取
    """
    post_data = {
        'post_id': None,
        'author_name': None,
        'author_id': None,
        'author_profile_url': None,
        'post_timestamp': None,
        'content_text': None,
        'content_html': None,
        'image_urls': [],
        'external_links': [],
        'iframe_urls': [],
        'floor': None,
        'user_title': '无头衔',
        'user_banners': [],
        'user_stats': {},
        'media_content': [],
        'permalink': None,
        'post_number': None,
        'total_reactions': 0
    }

    # 提取帖子ID
    if post_tag.has_attr('id') and 'post-' in post_tag['id']:
        try:
            post_data['post_id'] = int(str(post_tag['id']).split('-')[-1])
        except (ValueError, IndexError):
            pass
    
    # 也尝试从data-content属性获取
    if post_tag.has_attr('data-content'):
        post_id_attr = post_tag['data-content']
        if post_id_attr and str(post_id_attr).startswith('post-'):
            try:
                post_data['post_id'] = int(str(post_id_attr).split('-')[1])
            except (ValueError, IndexError):
                pass

    # 提取作者信息
    if post_tag.has_attr('data-author'):
        post_data['author_name'] = post_tag['data-author']
    
    # 从.message-cell--user区域提取更多作者信息
    user_cell = post_tag.select_one('.message-cell--user')
    if user_cell:
        username_tag = user_cell.select_one('.message-name .username')
        if username_tag:
            post_data['author_name'] = username_tag.get_text(strip=True)
            if username_tag.has_attr('data-user-id'):
                try:
                    post_data['author_id'] = int(str(username_tag['data-user-id']))
                except ValueError:
                    pass
        
        user_link_tag = user_cell.select_one('.message-avatar a, .message-name a')
        if user_link_tag and user_link_tag.has_attr('href'):
            post_data['author_profile_url'] = urljoin(base_url, str(user_link_tag['href']))

    # 提取用户头衔
    user_title_tag = post_tag.select_one('h5.userTitle')
    if user_title_tag:
        post_data['user_title'] = user_title_tag.get_text(strip=True)

    # 提取用户横幅
    user_banners = post_tag.select('div.userBanner')
    for banner in user_banners:
        banner_text = banner.get_text(strip=True)
        if banner_text:
            post_data['user_banners'].append(banner_text)

    # 提取用户统计信息
    user_stats_pairs = post_tag.select('div.message-userExtras dl.pairs')
    for pair in user_stats_pairs:
        dt = pair.select_one('dt')
        dd = pair.select_one('dd')
        if dt and dd:
            # 获取图标的含义
            icon_svg = dt.select_one('svg use')
            if icon_svg and icon_svg.has_attr('href'):
                icon_type = str(icon_svg['href']).split('#')[-1]
                post_data['user_stats'][icon_type] = dd.get_text(strip=True)

    # 提取时间戳和永久链接
    time_tag = post_tag.select_one('time.u-dt')
    if time_tag and isinstance(time_tag, Tag):
        if time_tag.has_attr('data-timestamp'):
            try:
                post_data['post_timestamp'] = int(str(time_tag['data-timestamp']))
            except ValueError:
                pass
        
        permalink_tag = time_tag.find_parent('a')
        if permalink_tag and isinstance(permalink_tag, Tag) and permalink_tag.has_attr('href'):
            relative_url = str(permalink_tag['href'])
            post_data['permalink'] = urljoin(base_url, relative_url)

    # 提取帖子编号/楼层号
    post_number_tag = post_tag.select_one('a[href*="post-"]')
    if post_number_tag:
        post_number_text = post_number_tag.get_text(strip=True)
        if post_number_text.startswith('#'):
            post_data['post_number'] = post_number_text
            try:
                post_data['floor'] = int(post_number_text.lstrip('#'))
            except ValueError:
                post_data['floor'] = post_number_text
    
    # 也尝试从message-attribution-opposite区域获取楼层
    floor_tag = post_tag.select_one('ul.message-attribution-opposite li:last-child a')
    if floor_tag:
        floor_text = floor_tag.get_text(strip=True)
        if floor_text.startswith('#'):
            try:
                post_data['floor'] = int(floor_text.lstrip('#'))
            except ValueError:
                post_data['floor'] = floor_text

    # 提取内容
    content_wrapper = post_tag.select_one('div.bbWrapper')
    if content_wrapper:
        post_data['content_text'] = content_wrapper.get_text(separator='\n', strip=True)
        post_data['content_html'] = str(content_wrapper)
        
        # 提取图片链接
        images = content_wrapper.select('img')
        for img in images:
            if img.has_attr('src') and not str(img['src']).startswith('data:'):
                # 优先使用data-url，如果没有则使用src
                img_url = img.get('data-url') or img.get('src')
                if img_url:
                    post_data['image_urls'].append(str(img_url))
                
                # 检查是否有父级链接包含原图地址
                parent_link = img.find_parent('a')
                
                image_data = {
                    'type': 'image',
                    'src': str(img['src']),  # 缩略图
                    'alt': img.get('alt', ''),
                    'class': img.get('class') or []
                }
                
                # 如果有父级链接，添加原图地址
                if parent_link and isinstance(parent_link, Tag) and parent_link.has_attr('href'):
                    image_data['original_url'] = str(parent_link['href'])  # 原图地址
                
                post_data['media_content'].append(image_data)
        
        # 提取外部链接
        external_links = content_wrapper.select('a.link--external')
        for link in external_links:
            if link.has_attr('href'):
                post_data['external_links'].append(str(link['href']))
        
        # 提取iframe视频链接
        iframes = content_wrapper.select('iframe')
        for iframe in iframes:
            if iframe.has_attr('src'):
                post_data['iframe_urls'].append(str(iframe['src']))
                post_data['media_content'].append({
                    'type': 'iframe',
                    'src': str(iframe['src']),
                    'class': iframe.get('class') or []
                })

    # 抓取reactions信息
    if enable_reactions and post_data['post_id'] and session:
        print(f"正在抓取帖子 {post_data['post_id']} 的reactions...")
        post_data['total_reactions'] = scrape_post_reactions(post_data['post_id'], base_url, session)

    return post_data

# 主要爬取函数
def scrape_xenforo_thread_with_requests(start_url: str, cookies: dict, enable_reactions: bool = True) -> List[Dict[str, Any]]:
    """
    爬取XenForo帖子的所有页面，并从每个帖子中提取详细信息。
    此版本直接在原函数内实现了增强的、健壮的帖子解析逻辑，并使用print进行状态输出。
    :param start_url: 帖子的起始URL（通常是第一页）。
    :param cookies: 用于登录会话的cookies字典。
    :return: 一个包含所有帖子数据的列表，每个帖子是一个字典。
             每个字典包含以下键:
             - 'post_id': 帖子ID (int | None)
             - 'author_name': 作者名 (str | None)
             - 'author_id': 作者ID (int | None)
             - 'author_profile_url': 作者主页链接 (str | None)
             - 'post_timestamp': 发布时间的Unix时间戳 (int | None)
             - 'content_text': 纯文本格式的帖子内容 (str | None)
             - 'content_html': 包含HTML标签的帖子内容 (str | None)
             - 'image_urls': 帖子中所有图片的URL列表 (List[str])
             - 'external_links': 帖子中所有外链的URL列表 (List[str])
             - 'iframe_urls': 帖子中所有iframe视频的URL列表 (List[str])
             - 'floor': 楼层号 (int | str | None)
    """
    base_url = urljoin(start_url, '/')
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)
    
    all_posts: List[Dict[str, Any]] = []
    current_url: Optional[str] = start_url
    page_num = 1
    total_posts_count = 0
    while current_url:
        print(f"正在爬取第 {page_num} 页: {current_url}")
        try:
            # 增加请求超时，提高程序健壮性
            response = session.get(current_url, timeout=15)
            response.raise_for_status() 
            soup = BeautifulSoup(response.text, 'html.parser')
            # 使用更精确的选择器，避免选中非帖子内容
            posts_on_page = soup.select('article.message.message--post')
            if not posts_on_page:
                print("在此页面上未找到帖子，爬取结束。")
                break
            print(f"在此页面找到 {len(posts_on_page)} 个帖子，正在解析...")
            for post_tag in posts_on_page:
                post_data = parse_post_enhanced(post_tag, base_url, session, enable_reactions)
                all_posts.append(post_data)
            total_posts_count += len(posts_on_page)
            # 翻页逻辑
            next_page_tag = soup.select_one('a.pageNav-jump--next')
            
            if next_page_tag and isinstance(next_page_tag, Tag) and next_page_tag.has_attr('href'):
                relative_url = str(next_page_tag['href'])
                current_url = urljoin(base_url, relative_url)
                page_num += 1
                # 维持原来的随机休眠
                sleep_duration = random.uniform(3, 7)
                print(f"找到下一页。为防止触发反爬，等待 {sleep_duration:.2f} 秒...")
                time.sleep(sleep_duration)
            else:
                print("未找到'Next'链接，已到达帖子末尾。")
                current_url = None
        except requests.exceptions.Timeout:
            print(f"网络请求超时，URL: {current_url}。请检查网络或增加超时时间。")
            break
        except requests.exceptions.RequestException as e:
            print(f"网络请求失败: {e}")
            break
        except Exception as e:
            print(f"处理页面时发生未知错误: {e}")
            break
    
    print(f"\n爬取完成！总共爬取了 {page_num-1 if page_num > 1 else 1} 页，获取了 {total_posts_count} 个帖子。")
    return all_posts


def save_posts_to_database(posts: List[Dict[str, Any]], thread_title: str, thread_url: str, 
                          db_manager: PostgreSQLManager, cookies: Optional[dict] = None) -> int:
    """
    将爬取的帖子数据保存到PostgreSQL数据库的新三表结构
    
    Args:
        posts: 爬取的帖子数据列表
        thread_title: 帖子标题
        thread_url: 帖子URL
        db_manager: PostgreSQL数据库管理器
    
    Returns:
        成功插入的记录数
    """
    if not posts:
        print("没有数据需要保存")
        return 0
    
    try:
        # 1. 检查线程是否存在，如果不存在则插入到 simpcity_thread_metadata 表
        thread_uuid = _ensure_thread_exists(thread_title, thread_url, db_manager, cookies)
        
        # 2. 插入帖子数据到 simpcity_thread_response 表
        insert_response_query = """
            INSERT INTO simpcity_thread_response (
                uuid, thread_uuid, post_id, author_name, author_id, 
                author_profile_url, post_timestamp, content_text, content_html,
                image_urls, external_links, iframe_urls, floor
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        insert_data = []
        post_uuids = []
        
        for post in posts:
            # 为每个帖子生成UUID
            post_uuid = str(uuid.uuid4())
            post_uuids.append((post_uuid, post.get('total_reactions', 0)))
            
            # 处理 floor 字段，确保是BIGINT兼容的数字类型
            floor_value = post.get('floor')
            if floor_value is not None:
                if isinstance(floor_value, str) and floor_value.isdigit():
                    floor_value = int(floor_value)
                elif not isinstance(floor_value, int):
                    floor_value = None
            
            # 将列表转换为JSONB格式
            image_urls_json = json.dumps(post.get('image_urls', []))
            external_links_json = json.dumps(post.get('external_links', []))
            iframe_urls_json = json.dumps(post.get('iframe_urls', []))
            
            row_data = (
                post_uuid,                              # uuid
                thread_uuid,                            # thread_uuid
                str(post.get('post_id')) if post.get('post_id') is not None else None,  # post_id
                post.get('author_name'),                # author_name
                str(post.get('author_id')) if post.get('author_id') is not None else None,  # author_id
                post.get('author_profile_url'),         # author_profile_url
                post.get('post_timestamp'),             # post_timestamp
                post.get('content_text'),               # content_text
                post.get('content_html'),               # content_html
                image_urls_json,                        # image_urls
                external_links_json,                    # external_links
                iframe_urls_json,                       # iframe_urls
                floor_value                             # floor
            )
            insert_data.append(row_data)
        
        # 批量插入帖子数据
        affected_rows = db_manager.execute_many(insert_response_query, insert_data)
        print(f"成功保存 {affected_rows} 条帖子记录到数据库")
        
        # 3. 插入反应数据到 simpcity_thread_reactions 表
        reactions_inserted = _save_reactions_to_database(post_uuids, db_manager)
        print(f"成功保存 {reactions_inserted} 条反应记录到数据库")
        
        return affected_rows
        
    except Exception as e:
        print(f"保存数据到数据库时发生错误: {e}")
        return 0


def _ensure_thread_exists(thread_title: str, thread_url: str, db_manager: PostgreSQLManager, 
                         cookies: Optional[dict] = None) -> str:
    """
    确保线程存在于 simpcity_thread_metadata 表中，如果不存在则插入
    
    Args:
        thread_title: 线程标题
        thread_url: 线程URL
        db_manager: 数据库管理器
        cookies: cookies字典，用于抓取元数据
    
    Returns:
        thread_uuid: 线程的UUID
    """
    try:
        # 首先检查线程是否已存在
        check_query = """
            SELECT uuid FROM simpcity_thread_metadata 
            WHERE url = %s AND is_deleted = false
        """
        existing_thread = db_manager.execute_one(check_query, (thread_url,))
        
        if existing_thread:
            # 线程已存在，返回其UUID
            return str(existing_thread['uuid'])
        
        # 线程不存在，创建新的线程记录
        thread_uuid = str(uuid.uuid4())
        
        # 尝试抓取完整的线程元数据
        metadata = None
        if cookies:
            try:
                metadata = extract_thread_metadata(thread_url, cookies)
                print(f"成功抓取线程元数据: {metadata}")
            except Exception as e:
                print(f"抓取线程元数据失败，使用基本信息: {e}")
        
        # 准备插入数据
        if metadata:
            insert_query = """
                INSERT INTO simpcity_thread_metadata (
                    uuid, name, categories, tags, url, avatar_img, description, create_time, update_time
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                )
            """
            
            # 将数组转换为PostgreSQL数组格式
            categories_array = metadata['categories'] if metadata['categories'] else None
            tags_array = metadata['tags'] if metadata['tags'] else None
            
            db_manager.execute_update(insert_query, (
                thread_uuid,
                metadata['title'] or thread_title,
                categories_array,
                tags_array,
                thread_url,
                metadata['avatar_img'],
                metadata['description']
            ))
            
            print(f"创建新线程记录: {metadata['title']} (Categories: {categories_array}, Tags: {tags_array})")
        else:
            # 如果没有元数据，使用基本信息
            insert_query = """
                INSERT INTO simpcity_thread_metadata (
                    uuid, name, url, create_time, update_time
                ) VALUES (
                    %s, %s, %s, NOW(), NOW()
                )
            """
            
            db_manager.execute_update(insert_query, (thread_uuid, thread_title, thread_url))
            print(f"创建新线程记录: {thread_title}")
        
        return thread_uuid
        
    except Exception as e:
        print(f"确保线程存在时发生错误: {e}")
        raise


def _save_reactions_to_database(post_uuids: List[tuple], db_manager: PostgreSQLManager) -> int:
    """
    将反应数据保存到 simpcity_thread_reactions 表
    
    Args:
        post_uuids: [(post_uuid, reactions_count), ...] 元组列表
        db_manager: 数据库管理器
    
    Returns:
        成功插入的记录数
    """
    if not post_uuids:
        return 0
    
    try:
        insert_query = """
            INSERT INTO simpcity_thread_reactions (
                uuid, post_uuid, reactions, create_time, update_time
            ) VALUES (
                %s, %s, %s, NOW(), NOW()
            )
        """
        
        insert_data = []
        for post_uuid, reactions_count in post_uuids:
            # 只插入有反应的帖子
            if reactions_count > 0:
                reaction_uuid = str(uuid.uuid4())
                insert_data.append((reaction_uuid, post_uuid, reactions_count))
        
        if insert_data:
            affected_rows = db_manager.execute_many(insert_query, insert_data)
            return affected_rows
        
        return 0
        
    except Exception as e:
        print(f"保存反应数据时发生错误: {e}")
        return 0


def extract_thread_metadata(thread_url: str, cookies: dict) -> Dict[str, Any]:
    """
    从帖子页面提取完整的线程元数据，包括标题、categories和tags
    
    Args:
        thread_url: 帖子URL
        cookies: cookies字典
    
    Returns:
        包含线程元数据的字典
    """
    metadata = {
        'title': None,
        'categories': [],
        'tags': [],
        'description': None,
        'avatar_img': None
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        session = requests.Session()
        session.headers.update(headers)
        session.cookies.update(cookies)
        
        response = session.get(thread_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 提取标题和categories
        title_element = soup.select_one('h1.p-title-value')
        if title_element:
            # 提取categories（标签）
            label_elements = title_element.select('span.label')
            for label in label_elements:
                category_text = label.get_text(strip=True)
                if category_text:
                    metadata['categories'].append(category_text)
            
            # 提取纯文本标题（去除标签部分）
            # 先移除所有的标签元素，然后获取剩余的文本
            title_copy = copy.copy(title_element)
            for label in title_copy.select('span.label'):
                label.decompose()
            for label_append in title_copy.select('span.label-append'):
                label_append.decompose()
            
            # 获取纯标题文本
            title_text = title_copy.get_text(strip=True)
            if title_text:
                metadata['title'] = title_text
        
        # 如果标题仍然为空，尝试其他方式
        if not metadata['title']:
            title_selectors = [
                'h1[data-xf-init="title-tooltip"]',
                'h1.thread-title',
                'title'
            ]
            
            for selector in title_selectors:
                title_tag = soup.select_one(selector)
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    if title and title != 'title':
                        metadata['title'] = title
                        break
        
        # 2. 提取tags
        tag_list = soup.select_one('dl.tagList')
        if tag_list:
            tag_elements = tag_list.select('a.tagItem')
            for tag_element in tag_elements:
                tag_text = tag_element.get_text(strip=True)
                if tag_text:
                    metadata['tags'].append(tag_text)
        
        # 3. 提取描述信息（如果存在）
        description_element = soup.select_one('.p-description, .thread-description')
        if description_element:
            metadata['description'] = description_element.get_text(strip=True)
        
        # 4. 提取头像/封面图片（如果存在）
        avatar_element = soup.select_one('.p-title-pageAction img, .thread-avatar img')
        if avatar_element and avatar_element.has_attr('src'):
            metadata['avatar_img'] = avatar_element['src']
        
        # 如果标题仍然为空，使用URL作为标题
        if not metadata['title']:
            metadata['title'] = thread_url.split('/')[-1] or "未知标题"
        
        print(f"提取线程元数据成功: 标题={metadata['title']}, Categories={metadata['categories']}, Tags={metadata['tags']}")
        
        return metadata
        
    except Exception as e:
        print(f"提取线程元数据时发生错误: {e}")
        # 返回默认值
        metadata['title'] = thread_url.split('/')[-1] or "未知标题"
        return metadata


def extract_thread_title(thread_url: str, cookies: dict) -> str:
    """
    从帖子页面提取标题（保持向后兼容）
    
    Args:
        thread_url: 帖子URL
        cookies: cookies字典
    
    Returns:
        帖子标题，如果提取失败返回默认值
    """
    metadata = extract_thread_metadata(thread_url, cookies)
    return metadata['title']

def crawler(thread_url: str, cookies: dict, thread_title: Optional[str] = None, 
           enable_reactions: bool = True, save_to_db: bool = True, 
           config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    综合爬取方法：爬取XenForo帖子并可选地存储到PostgreSQL数据库
    
    Args:
        thread_url: 要爬取的帖子URL
        cookies: 用于登录会话的cookies字典
        thread_title: 帖子标题（可选，如果不提供会尝试从页面提取）
        enable_reactions: 是否启用reactions抓取，默认True
        save_to_db: 是否保存到数据库，默认True
        config_path: 数据库配置文件路径，默认"config.yaml"
    
    Returns:
        包含爬取结果的字典：
        {
            'success': bool,          # 是否成功
            'posts': List[Dict],      # 爬取的帖子数据
            'total_posts': int,       # 总帖子数
            'thread_title': str,      # 帖子标题
            'thread_url': str,        # 帖子URL
            'db_records': int,        # 保存到数据库的记录数（如果启用）
            'error': str              # 错误信息（如果失败）
        }
    """
    result = {
        'success': False,
        'posts': [],
        'total_posts': 0,
        'thread_title': thread_title or "未知标题",
        'thread_url': thread_url,
        'db_records': 0,
        'error': None
    }
    
    try:
        print(f"开始爬取帖子: {thread_url}")
        print(f"Reactions抓取: {'启用' if enable_reactions else '禁用'}")
        print(f"数据库存储: {'启用' if save_to_db else '禁用'}")
        
        # 如果没有提供标题，尝试从页面提取
        if not thread_title:
            thread_title = extract_thread_title(thread_url, cookies)
        
        # 确保thread_title不为None
        if not thread_title:
            thread_title = "未知标题"
        
        result['thread_title'] = thread_title
        
        # 爬取帖子数据
        posts = scrape_xenforo_thread_with_requests(thread_url, cookies, enable_reactions)
        
        if not posts:
            result['error'] = "未能获取到任何帖子数据"
            return result
        
        result['posts'] = posts
        result['total_posts'] = len(posts)
        result['success'] = True
        
        print(f"爬取完成，共获取 {len(posts)} 个帖子")
        
        # 如果启用数据库存储
        if save_to_db:
            print("正在保存数据到数据库...")
            db_manager = PostgreSQLManager(config_path)
            try:
                db_records = save_posts_to_database(posts, thread_title, thread_url, db_manager, cookies)
                result['db_records'] = db_records
                print(f"数据库操作完成，保存了 {db_records} 条记录")
            finally:
                db_manager.close_all_connections()
        
        return result
        
    except Exception as e:
        error_msg = f"爬取过程中发生错误: {str(e)}"
        print(error_msg)
        result['error'] = error_msg
        return result


def sync(thread_url: str, cookies: dict, thread_title: Optional[str] = None, 
           enable_reactions: bool = True, save_to_db: bool = True, 
           config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    同步simpcity帖子
    
    Args:
        thread_url: 要同步的帖子URL
        cookies: 用于登录会话的cookies字典
        thread_title: 帖子标题（可选）
        enable_reactions: 是否启用reactions抓取，默认True
        save_to_db: 是否保存到数据库，默认True
        config_path: 数据库配置文件路径
    
    Returns:
        包含同步结果的字典：
        {
            'success': bool,          # 是否成功
            'thread_title': str,      # 帖子标题
            'thread_url': str,        # 帖子URL
            'new_posts': int,         # 新增帖子数
            'updated_posts': int,     # 更新帖子数
            'deleted_posts': int,     # 删除帖子数
            'unchanged_posts': int,   # 未变化帖子数
            'total_posts': int,       # 爬取到的总帖子数
            'db_records': int,        # 数据库操作记录数（新增+更新+删除）
            'error': str              # 错误信息（如果失败）
        }
    """
    result = {
        'success': False,
        'thread_title': thread_title or "未知标题",
        'thread_url': thread_url,
        'new_posts': 0,
        'updated_posts': 0,
        'deleted_posts': 0,
        'unchanged_posts': 0,
        'total_posts': 0,
        'db_records': 0,
        'error': None
    }
    
    try:
        print(f"开始同步帖子: {thread_url}")
        
        # 如果没有提供标题，尝试从页面提取
        if not thread_title:
            thread_title = extract_thread_title(thread_url, cookies)
        
        if not thread_title:
            thread_title = "未知标题"
        
        result['thread_title'] = thread_title
        
        # 1. 爬取thread的全量数据
        print("正在爬取最新数据...")
        new_posts = scrape_xenforo_thread_with_requests(thread_url, cookies, enable_reactions)
        
        if not new_posts:
            result['error'] = "未能获取到任何帖子数据"
            return result
        
        # 设置总帖子数
        result['total_posts'] = len(new_posts)
        
        # 如果不需要保存到数据库，直接返回
        if not save_to_db:
            result['success'] = True
            result['new_posts'] = len(new_posts)
            return result
        
        # 2. 从数据库中查询现有数据
        db_manager = PostgreSQLManager(config_path)
        try:
            # 首先获取线程UUID
            thread_check_query = """
                SELECT uuid FROM simpcity_thread_metadata 
                WHERE url = %s AND is_deleted = false
            """
            thread_result = db_manager.execute_one(thread_check_query, (thread_url,))
            
            if not thread_result:
                # 线程不存在，所有帖子都是新的
                result['new_posts'] = len(new_posts)
                result['total_posts'] = len(new_posts)
                result['success'] = True
                
                if save_to_db:
                    db_records = _save_posts_to_database_sync(new_posts, thread_title, thread_url, db_manager, cookies)
                    result['db_records'] = db_records
                
                return result
            
            thread_uuid = str(thread_result['uuid'])
            
            # 根据thread_uuid查询现有数据
            existing_query = """
                SELECT post_id, author_name, author_id, floor, content_text, content_html,
                       image_urls, external_links, iframe_urls, post_timestamp, author_profile_url
                FROM simpcity_thread_response 
                WHERE thread_uuid = %s AND is_deleted = false
                ORDER BY floor ASC
            """
            existing_posts = db_manager.execute_query(existing_query, (thread_uuid,))
            
            # 将现有数据转换为以floor为key的字典，方便查找
            existing_posts_dict = {}
            for post in existing_posts:
                floor_key = post['floor']
                if floor_key is not None:
                    existing_posts_dict[floor_key] = post
            
            # 3. 对比新旧数据
            print("正在对比数据差异...")
            
            # 新爬取的数据转换为以floor为key的字典
            new_posts_dict = {}
            for post in new_posts:
                floor_key = post.get('floor')
                if floor_key is not None:
                    new_posts_dict[floor_key] = post
            
            # 找出新增、修改、未变化的帖子
            new_post_list = []
            updated_post_list = []
            unchanged_count = 0
            
            for floor, new_post in new_posts_dict.items():
                if floor not in existing_posts_dict:
                    # 新增帖子
                    new_post_list.append(new_post)
                else:
                    # 检查是否有修改
                    existing_post = existing_posts_dict[floor]
                    if _is_post_changed(new_post, existing_post):
                        updated_post_list.append(new_post)
                    else:
                        unchanged_count += 1
            
            # 找出已删除的帖子（在原数据中存在但在新数据中不存在）
            deleted_floors = set(existing_posts_dict.keys()) - set(new_posts_dict.keys())
            
            # 4. 执行数据库操作
            print(f"发现变化：新增{len(new_post_list)}个，更新{len(updated_post_list)}个，删除{len(deleted_floors)}个，未变化{unchanged_count}个")
            
            # 插入新增的帖子
            if new_post_list:
                new_records = _save_posts_to_database_sync(new_post_list, thread_title, thread_url, db_manager, cookies)
                result['new_posts'] = new_records
                print(f"新增了 {new_records} 条记录")
            
            # 更新修改的帖子
            if updated_post_list:
                updated_records = _update_posts_in_database(updated_post_list, thread_title, thread_url, db_manager, cookies)
                result['updated_posts'] = updated_records
                print(f"更新了 {updated_records} 条记录")
            
            # 标记删除的帖子
            if deleted_floors:
                deleted_records = _mark_posts_as_deleted(deleted_floors, thread_url, thread_title, db_manager, cookies)
                result['deleted_posts'] = deleted_records
                print(f"标记删除了 {deleted_records} 条记录")
            
            result['unchanged_posts'] = unchanged_count
            result['db_records'] = result['new_posts'] + result['updated_posts'] + result['deleted_posts']
            result['success'] = True
            
            print(f"同步完成：新增{result['new_posts']}，更新{result['updated_posts']}，删除{result['deleted_posts']}，未变化{result['unchanged_posts']}")
            
        finally:
            db_manager.close_all_connections()
        
        return result
        
    except Exception as e:
        error_msg = f"同步过程中发生错误: {str(e)}"
        print(error_msg)
        result['error'] = error_msg
        return result

def watch(thread_url: str, cookies: dict, 
          schedule_type: str = "interval", 
          interval_minutes: int = 60,
          cron_expression: Optional[str] = None,
          thread_title: Optional[str] = None,
          enable_reactions: bool = True,
          save_to_db: bool = True,
          config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    监控simpcity帖子，定时执行同步操作
    
    Args:
        thread_url: 要监控的帖子URL
        cookies: 用于登录会话的cookies字典
        schedule_type: 调度类型，支持 "interval" 或 "cron"
        interval_minutes: 间隔时间（分钟），仅当schedule_type为"interval"时有效
        cron_expression: cron表达式，仅当schedule_type为"cron"时有效
        thread_title: 帖子标题（可选）
        enable_reactions: 是否启用reactions抓取，默认True
        save_to_db: 是否保存到数据库，默认True
        config_path: 数据库配置文件路径
    
    Returns:
        包含监控器信息的字典，包含启动/停止方法
    
    Example:
        # 使用间隔调度，每30分钟同步一次
        watcher = watch(
            thread_url="https://example.com/thread/123",
            cookies={"session": "abc123"},
            schedule_type="interval",
            interval_minutes=30
        )
        
        # 使用cron表达式，每天早上8点同步
        watcher = watch(
            thread_url="https://example.com/thread/123", 
            cookies={"session": "abc123"},
            schedule_type="cron",
            cron_expression="0 8 * * *"
        )
        
        # 启动监控
        watcher['start']()
        
        # 停止监控
        watcher['stop']()
    """
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # 创建调度器
    scheduler = BackgroundScheduler()
    
    # 监控状态
    watch_info = {
        'thread_url': thread_url,
        'thread_title': thread_title,
        'schedule_type': schedule_type,
        'interval_minutes': interval_minutes,
        'cron_expression': cron_expression,
        'is_running': False,
        'last_sync_time': None,
        'last_sync_result': None,
        'sync_count': 0,
        'error_count': 0,
        'scheduler': scheduler
    }
    
    def sync_job():
        """执行同步任务的内部方法"""
        try:
            logger.info(f"开始定时同步任务 - URL: {thread_url}")
            
            # 执行同步
            result = sync(
                thread_url=thread_url,
                cookies=cookies,
                thread_title=thread_title,
                enable_reactions=enable_reactions,
                save_to_db=save_to_db,
                config_path=config_path
            )
            
            # 更新监控信息
            watch_info['last_sync_time'] = datetime.now()
            watch_info['last_sync_result'] = result
            watch_info['sync_count'] += 1
            
            if result['success']:
                logger.info(f"同步任务完成 - 新增:{result['new_posts']} 更新:{result['updated_posts']} 删除:{result['deleted_posts']}")
            else:
                logger.error(f"同步任务失败: {result.get('error', '未知错误')}")
                watch_info['error_count'] += 1
                
        except Exception as e:
            logger.error(f"执行同步任务时发生异常: {str(e)}")
            watch_info['error_count'] += 1
            watch_info['last_sync_result'] = {
                'success': False,
                'error': str(e)
            }
    
    def job_listener(event):
        """作业事件监听器"""
        if event.exception:
            logger.error(f"定时任务执行异常: {event.exception}")
        else:
            logger.info("定时任务执行成功")
    
    # 添加作业监听器
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    # 根据调度类型配置触发器
    if schedule_type == "interval":
        if interval_minutes <= 0:
            raise ValueError("interval_minutes 必须大于0")
        
        trigger = IntervalTrigger(minutes=interval_minutes)
        job_id = f"sync_{hash(thread_url)}_interval_{interval_minutes}"
        logger.info(f"配置间隔调度: 每{interval_minutes}分钟执行一次")
        
    elif schedule_type == "cron":
        if not cron_expression:
            raise ValueError("使用cron调度类型时必须提供cron_expression")
        
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
            job_id = f"sync_{hash(thread_url)}_cron_{hash(cron_expression)}"
            logger.info(f"配置cron调度: {cron_expression}")
        except Exception as e:
            raise ValueError(f"无效的cron表达式: {cron_expression}, 错误: {e}")
    
    else:
        raise ValueError(f"不支持的调度类型: {schedule_type}，仅支持 'interval' 或 'cron'")
    
    # 添加作业到调度器
    scheduler.add_job(
        func=sync_job,
        trigger=trigger,
        id=job_id,
        name=f"SimpCity同步任务 - {thread_title or thread_url}",
        replace_existing=True,
        max_instances=1  # 防止重复执行
    )
    
    def start_watch():
        """启动监控"""
        if not watch_info['is_running']:
            try:
                scheduler.start()
                watch_info['is_running'] = True
                logger.info(f"监控已启动 - {thread_title or thread_url}")
                
                # 可选：立即执行一次同步
                logger.info("立即执行首次同步...")
                sync_job()
                
            except Exception as e:
                logger.error(f"启动监控失败: {e}")
                raise
        else:
            logger.warning("监控已经在运行中")
    
    def stop_watch():
        """停止监控"""
        if watch_info['is_running']:
            try:
                scheduler.shutdown()
                watch_info['is_running'] = False
                logger.info(f"监控已停止 - {thread_title or thread_url}")
            except Exception as e:
                logger.error(f"停止监控失败: {e}")
                raise
        else:
            logger.warning("监控未在运行")
    
    def get_status():
        """获取监控状态"""
        # 安全地获取下次运行时间
        next_run_time = None
        if watch_info['is_running']:
            job = scheduler.get_job(job_id)
            if job:
                next_run_time = job.next_run_time
        
        return {
            'is_running': watch_info['is_running'],
            'thread_url': watch_info['thread_url'],
            'thread_title': watch_info['thread_title'],
            'schedule_type': watch_info['schedule_type'],
            'interval_minutes': watch_info['interval_minutes'],
            'cron_expression': watch_info['cron_expression'],
            'last_sync_time': watch_info['last_sync_time'],
            'last_sync_result': watch_info['last_sync_result'],
            'sync_count': watch_info['sync_count'],
            'error_count': watch_info['error_count'],
            'next_run_time': next_run_time
        }
    
    def force_sync():
        """强制执行一次同步"""
        logger.info("手动触发同步任务...")
        sync_job()
    
    # 返回监控器对象
    return {
        'start': start_watch,
        'stop': stop_watch,
        'status': get_status,
        'force_sync': force_sync,
        'info': watch_info
    }

def _is_post_changed(new_post: Dict[str, Any], existing_post: Dict[str, Any]) -> bool:
    """
    判断帖子是否有变化
    
    Args:
        new_post: 新爬取的帖子数据
        existing_post: 数据库中现有的帖子数据
    
    Returns:
        True表示有变化，False表示无变化
    """
    # 比较关键字段
    fields_to_compare = [
        'author_name', 'author_id', 'content_text', 'content_html',
        'post_timestamp', 'author_profile_url'
    ]
    
    for field in fields_to_compare:
        new_value = new_post.get(field)
        existing_value = existing_post.get(field)
        
        # 处理None值的比较
        if new_value != existing_value:
            return True
    
    # 比较列表字段（需要将JSON字符串转换为列表比较）
    list_fields = ['image_urls', 'external_links', 'iframe_urls']
    for field in list_fields:
        new_value = new_post.get(field, [])
        existing_value = existing_post.get(field)
        
        # 如果existing_value是JSON字符串，需要解析
        if isinstance(existing_value, str):
            try:
                existing_value = json.loads(existing_value)
            except (json.JSONDecodeError, TypeError):
                existing_value = []
        elif existing_value is None:
            existing_value = []
        
        if new_value != existing_value:
            return True
    
    return False


def _save_posts_to_database_sync(posts: List[Dict[str, Any]], thread_title: str, 
                                thread_url: str, db_manager: PostgreSQLManager, cookies: Optional[dict] = None) -> int:
    """
    保存新增的帖子到数据库（同步版本）- 适配新的三表结构
    """
    if not posts:
        return 0
    
    try:
        # 1. 确保线程存在
        thread_uuid = _ensure_thread_exists(thread_title, thread_url, db_manager, cookies)
        
        # 2. 插入帖子数据
        insert_query = """
            INSERT INTO simpcity_thread_response (
                uuid, thread_uuid, post_id, author_name, author_id, 
                author_profile_url, post_timestamp, content_text, content_html,
                image_urls, external_links, iframe_urls, floor
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        insert_data = []
        post_uuids = []
        
        for post in posts:
            # 生成帖子UUID
            post_uuid = str(uuid.uuid4())
            post_uuids.append((post_uuid, post.get('total_reactions', 0)))
            
            # 处理floor字段
            floor_value = post.get('floor')
            if floor_value is not None:
                if isinstance(floor_value, str) and floor_value.isdigit():
                    floor_value = int(floor_value)
                elif not isinstance(floor_value, int):
                    floor_value = None
            
            # 将列表转换为JSON字符串
            image_urls_json = json.dumps(post.get('image_urls', []))
            external_links_json = json.dumps(post.get('external_links', []))
            iframe_urls_json = json.dumps(post.get('iframe_urls', []))
            
            row_data = (
                post_uuid,                                # uuid
                thread_uuid,                              # thread_uuid
                str(post.get('post_id')) if post.get('post_id') is not None else None,  # post_id
                post.get('author_name'),                  # author_name
                str(post.get('author_id')) if post.get('author_id') is not None else None,  # author_id
                post.get('author_profile_url'),           # author_profile_url
                post.get('post_timestamp'),               # post_timestamp
                post.get('content_text'),                 # content_text
                post.get('content_html'),                 # content_html
                image_urls_json,                          # image_urls
                external_links_json,                      # external_links
                iframe_urls_json,                         # iframe_urls
                floor_value                               # floor
            )
            insert_data.append(row_data)
        
        # 批量插入帖子数据
        affected_rows = db_manager.execute_many(insert_query, insert_data)
        
        # 3. 插入反应数据
        _save_reactions_to_database(post_uuids, db_manager)
        
        return affected_rows
        
    except Exception as e:
        print(f"同步保存帖子数据时发生错误: {e}")
        return 0


def _update_posts_in_database(posts: List[Dict[str, Any]], thread_title: str, 
                             thread_url: str, db_manager: PostgreSQLManager, cookies: Optional[dict] = None) -> int:
    """
    更新修改的帖子到数据库 - 适配新的三表结构
    """
    if not posts:
        return 0
    
    try:
        # 1. 确保线程存在
        thread_uuid = _ensure_thread_exists(thread_title, thread_url, db_manager, cookies)
        
        # 2. 更新帖子数据
        update_query = """
            UPDATE simpcity_thread_response SET
                post_id = %s, author_name = %s, author_id = %s, 
                author_profile_url = %s, post_timestamp = %s, 
                content_text = %s, content_html = %s, image_urls = %s, 
                external_links = %s, iframe_urls = %s, update_time = NOW()
            WHERE thread_uuid = %s AND floor = %s
        """
        
        updated_count = 0
        
        for post in posts:
            # 处理floor字段
            floor_value = post.get('floor')
            if floor_value is not None:
                if isinstance(floor_value, str) and floor_value.isdigit():
                    floor_value = int(floor_value)
                elif not isinstance(floor_value, int):
                    floor_value = None
            
            # 将列表转换为JSON字符串
            image_urls_json = json.dumps(post.get('image_urls', []))
            external_links_json = json.dumps(post.get('external_links', []))
            iframe_urls_json = json.dumps(post.get('iframe_urls', []))
            
            row_data = (
                str(post.get('post_id')) if post.get('post_id') is not None else None,  # post_id
                post.get('author_name'),                  # author_name
                str(post.get('author_id')) if post.get('author_id') is not None else None,  # author_id
                post.get('author_profile_url'),           # author_profile_url
                post.get('post_timestamp'),               # post_timestamp
                post.get('content_text'),                 # content_text
                post.get('content_html'),                 # content_html
                image_urls_json,                          # image_urls
                external_links_json,                      # external_links
                iframe_urls_json,                         # iframe_urls
                thread_uuid,                              # thread_uuid
                floor_value                               # floor
            )
            
            updated_count += db_manager.execute_update(update_query, row_data)
            
            # 3. 更新反应数据
            _update_reactions_in_database(post, thread_uuid, db_manager)
        
        return updated_count
        
    except Exception as e:
        print(f"更新帖子数据时发生错误: {e}")
        return 0


def _update_reactions_in_database(post: Dict[str, Any], thread_uuid: str, db_manager: PostgreSQLManager) -> int:
    """
    更新帖子的反应数据
    
    Args:
        post: 帖子数据
        thread_uuid: 线程UUID
        db_manager: 数据库管理器
    
    Returns:
        更新的记录数
    """
    try:
        floor_value = post.get('floor')
        reactions_count = post.get('total_reactions', 0)
        
        if floor_value is None or reactions_count <= 0:
            return 0
        
        # 首先获取帖子的UUID
        get_post_query = """
            SELECT uuid FROM simpcity_thread_response 
            WHERE thread_uuid = %s AND floor = %s
        """
        post_result = db_manager.execute_one(get_post_query, (thread_uuid, floor_value))
        
        if not post_result:
            return 0
        
        post_uuid = str(post_result['uuid'])
        
        # 检查反应记录是否存在
        check_reaction_query = """
            SELECT uuid FROM simpcity_thread_reactions 
            WHERE post_uuid = %s
        """
        existing_reaction = db_manager.execute_one(check_reaction_query, (post_uuid,))
        
        if existing_reaction:
            # 更新现有反应记录
            update_reaction_query = """
                UPDATE simpcity_thread_reactions 
                SET reactions = %s, update_time = NOW()
                WHERE post_uuid = %s
            """
            return db_manager.execute_update(update_reaction_query, (reactions_count, post_uuid))
        else:
            # 插入新的反应记录
            reaction_uuid = str(uuid.uuid4())
            insert_reaction_query = """
                INSERT INTO simpcity_thread_reactions (
                    uuid, post_uuid, reactions, create_time, update_time
                ) VALUES (
                    %s, %s, %s, NOW(), NOW()
                )
            """
            return db_manager.execute_update(insert_reaction_query, (reaction_uuid, post_uuid, reactions_count))
    
    except Exception as e:
        print(f"更新反应数据时发生错误: {e}")
        return 0


def _mark_posts_as_deleted(deleted_floors: set, thread_url: str, thread_title: str, 
                          db_manager: PostgreSQLManager, cookies: Optional[dict] = None) -> int:
    """
    标记删除的帖子 - 适配新的三表结构
    """
    if not deleted_floors:
        return 0
    
    try:
        # 1. 确保线程存在
        thread_uuid = _ensure_thread_exists(thread_title, thread_url, db_manager, cookies)
        
        # 2. 标记帖子为删除状态
        placeholders = ','.join(['%s'] * len(deleted_floors))
        update_query = f"""
            UPDATE simpcity_thread_response 
            SET is_deleted = TRUE, delete_time = NOW(), update_time = NOW()
            WHERE thread_uuid = %s AND floor IN ({placeholders})
        """
        
        # 准备参数
        params = [thread_uuid] + list(deleted_floors)
        
        return db_manager.execute_update(update_query, tuple(params))
        
    except Exception as e:
        print(f"标记删除失败: {e}")
        return 0





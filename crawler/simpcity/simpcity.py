import requests
from bs4 import BeautifulSoup, Tag
import time
import random
import json

from urllib.parse import urljoin
from typing import Dict, Any, Optional, List

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
                          db_manager: PostgreSQLManager) -> int:
    """
    将爬取的帖子数据保存到PostgreSQL数据库
    
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
    
    insert_query = """
        INSERT INTO simpcity (
            thread, thread_url, post_id, author_name, author_id, 
            author_profile_url, post_timestamp, content_text, content_html,
            image_urls, external_links, iframe_urls, floor
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """
    
    insert_data = []
    for post in posts:
        # 处理 floor 字段，确保是数字类型
        floor_value = post.get('floor')
        if floor_value is not None:
            if isinstance(floor_value, str) and floor_value.isdigit():
                floor_value = int(floor_value)
            elif not isinstance(floor_value, int):
                floor_value = None
        
        # 将列表转换为JSON字符串用于JSONB字段
        image_urls_json = json.dumps(post.get('image_urls', []))
        external_links_json = json.dumps(post.get('external_links', []))
        iframe_urls_json = json.dumps(post.get('iframe_urls', []))
        
        row_data = (
            thread_title,                           # thread
            thread_url,                             # thread_url
            post.get('post_id'),                    # post_id
            post.get('author_name'),                # author_name
            post.get('author_id'),                  # author_id
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
    
    try:
        # 使用批量插入
        affected_rows = db_manager.execute_many(insert_query, insert_data)
        print(f"成功保存 {affected_rows} 条记录到数据库")
        return affected_rows
    except Exception as e:
        print(f"保存数据到数据库时发生错误: {e}")
        return 0


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
                db_records = save_posts_to_database(posts, thread_title, thread_url, db_manager)
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


def extract_thread_title(thread_url: str, cookies: dict) -> str:
    """
    从帖子页面提取标题
    
    Args:
        thread_url: 帖子URL
        cookies: cookies字典
    
    Returns:
        帖子标题，如果提取失败返回默认值
    """
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
        
        # 尝试多种方式提取标题
        title_selectors = [
            'h1.p-title-value',
            'h1[data-xf-init="title-tooltip"]',
            'h1.thread-title',
            'title'
        ]
        
        for selector in title_selectors:
            title_tag = soup.select_one(selector)
            if title_tag:
                title = title_tag.get_text(strip=True)
                if title and title != 'title':
                    return title
        
        # 如果都没找到，使用URL作为标题
        return thread_url.split('/')[-1] or "未知标题"
        
    except Exception as e:
        print(f"提取标题时发生错误: {e}")
        return thread_url.split('/')[-1] or "未知标题"


# 使用示例
if __name__ == "__main__":
    # 示例用法
    sample_cookies = {
        'session_id': 'your_session_id',
        # 添加其他必要的cookies
    }
    
    sample_url = "https://simpcity.su/threads/example-thread.123456/"
    
    # 完整爬取并存储到数据库
    result = crawler(
        thread_url=sample_url,
        cookies=sample_cookies,
        thread_title="示例帖子标题",
        enable_reactions=True,
        save_to_db=True
    )
    
    print("爬取结果:")
    print(f"成功: {result['success']}")
    print(f"总帖子数: {result['total_posts']}")
    print(f"数据库记录数: {result['db_records']}")
    if result['error']:
        print(f"错误: {result['error']}")




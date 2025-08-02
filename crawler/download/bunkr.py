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
import logging
import re
import os
import base64
import hashlib
import asyncio
import aiohttp
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs, unquote, urlunparse
from typing import Dict, Any, Optional, List, Union, Tuple
import mimetypes
from pathlib import Path
from itertools import cycle
from math import floor
import html


class BunkrConfig:
    """Bunkr下载器配置类"""
    
    # API端点
    BUNKR_API = "https://bunkr.cr/api/vs"
    STATUS_PAGE = "https://status.bunkr.ru/"
    
    # 文件大小常量
    KB = 1024
    MB = 1024 * KB
    GB = 1024 * MB
    
    # 下载块大小阈值
    THRESHOLDS = [
        (1 * MB, 32 * KB),    # 小于1MB
        (10 * MB, 128 * KB),  # 1MB到10MB
        (50 * MB, 512 * KB),  # 10MB到50MB
        (100 * MB, 1 * MB),   # 50MB到100MB
        (250 * MB, 2 * MB),   # 100MB到250MB
        (500 * MB, 4 * MB),   # 250MB到500MB
        (1 * GB, 8 * MB),     # 500MB到1GB
    ]
    
    # 大文件默认块大小
    LARGE_FILE_CHUNK_SIZE = 16 * MB
    
    # HTTP状态码
    HTTP_STATUS_OK = 200
    HTTP_STATUS_FORBIDDEN = 403
    HTTP_STATUS_BAD_GATEWAY = 502
    HTTP_STATUS_SERVER_DOWN = 521
    
    # 请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6,sv;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    # 下载专用请求头
    DOWNLOAD_HEADERS = {
        **HEADERS,
        "Referer": "https://get.bunkrr.su/",
    }
    
    # 正则表达式
    VALID_SLUG_REGEX = r"^[a-zA-Z0-9_-]+$"
    MEDIA_SLUG_REGEX = r'const\s+slug\s*=\s*"([a-zA-Z0-9_-]+)"'
    
    # 最大文件名长度
    MAX_FILENAME_LEN = 120
    
    # 最大重试次数
    MAX_RETRIES = 5


class BunkrStatusManager:
    """Bunkr服务器状态管理器"""
    
    def __init__(self):
        self.status_cache = {}
        self.last_update = 0
        self.cache_duration = 300  # 5分钟缓存
    
    def get_bunkr_status(self) -> Dict[str, str]:
        """获取bunkr服务器状态"""
        current_time = time.time()
        
        # 检查缓存是否有效
        if current_time - self.last_update < self.cache_duration and self.status_cache:
            return self.status_cache
        
        try:
            response = requests.get(BunkrConfig.STATUS_PAGE, headers=BunkrConfig.HEADERS, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            bunkr_status = {}
            
            server_items = soup.find_all(
                "div",
                {"class": "flex items-center gap-4 py-4 border-b border-soft last:border-b-0"}
            )
            
            for server_item in server_items:
                try:
                    server_name = server_item.find("p").get_text(strip=True)
                    server_status = server_item.find("span").get_text(strip=True)
                    bunkr_status[server_name] = server_status
                except AttributeError:
                    continue
            
            self.status_cache = bunkr_status
            self.last_update = current_time
            return bunkr_status
            
        except Exception as e:
            logging.warning(f"获取服务器状态失败: {e}")
            return self.status_cache or {}
    
    def get_offline_servers(self) -> Dict[str, str]:
        """获取离线服务器列表"""
        bunkr_status = self.get_bunkr_status()
        return {
            server_name: server_status
            for server_name, server_status in bunkr_status.items()
            if server_status != "Operational"
        }
    
    def get_subdomain(self, download_link: str) -> str:
        """从URL中提取子域名"""
        netloc = urlparse(download_link).netloc
        return netloc.split(".")[0].capitalize()
    
    def subdomain_is_offline(self, download_link: str) -> bool:
        """检查子域名是否离线"""
        offline_servers = self.get_offline_servers()
        subdomain = self.get_subdomain(download_link)
        return subdomain in offline_servers
    
    def mark_subdomain_as_offline(self, download_link: str) -> str:
        """标记子域名为离线状态"""
        subdomain = self.get_subdomain(download_link)
        self.status_cache[subdomain] = "Non-operational"
        return subdomain


class BunkrDownloader:
    """Bunkr下载器类，支持从bunkr网站下载图片和视频"""
    
    def __init__(self, download_dir: str = "downloads", session: Optional[requests.Session] = None):
        """
        初始化下载器
        
        Args:
            download_dir: 下载目录
            session: 可选的requests session
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
        # 设置session
        if session is None:
            self.session = requests.Session()
            self.session.headers.update(BunkrConfig.HEADERS)
        else:
            self.session = session
        
        # 配置日志
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # 初始化状态管理器
        self.status_manager = BunkrStatusManager()
        
        # bunkr域名正则表达式
        self.bunkr_pattern = re.compile(r'bunkr\.\w+')
    
    def is_bunkr_url(self, url: str) -> bool:
        """
        检查URL是否为bunkr相关地址
        
        Args:
            url: 要检查的URL
            
        Returns:
            True如果是bunkr URL
        """
        return bool(self.bunkr_pattern.search(url))
    
    def get_url_type(self, url: str) -> str:
        """
        判断URL类型
        
        Args:
            url: bunkr URL
            
        Returns:
            'album' 表示 /a/ 类型（资源列表）
            'file' 表示 /f/ 类型（单个文件）
            'video' 表示 /v/ 类型（视频文件）
            'unknown' 表示未知类型
        """
        url_mapping = {"a": "album", "f": "file", "v": "video"}
        
        try:
            url_type = url.split("/")[-2]
            return url_mapping.get(url_type, "unknown")
        except IndexError:
            return "unknown"
    
    def change_domain_to_cr(self, url: str) -> str:
        """
        将域名更改为bunkr.cr（用于重试）
        
        Args:
            url: 原始URL
            
        Returns:
            使用bunkr.cr域名的URL
        """
        parsed = urlparse(url)
        new_parsed = parsed._replace(netloc="bunkr.cr")
        return urlunparse(new_parsed)
    
    def get_host_page(self, url: str) -> str:
        """获取主机页面URL"""
        url_netloc = urlparse(url).netloc
        return f"https://{url_netloc}"
    
    def extract_file_links_from_album(self, album_url: str) -> List[str]:
        """
        从相册页面提取所有文件链接
        
        Args:
            album_url: 相册URL (/a/ 类型)
            
        Returns:
            文件URL列表
        """
        try:
            self.logger.info(f"正在提取相册链接: {album_url}")
            
            response = self.session.get(album_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找所有文件链接
            file_links = []
            link_elements = soup.find_all(
                "a", 
                {"class": "after:absolute after:z-10 after:inset-0", "href": True}
            )
            
            host_page = self.get_host_page(album_url)
            
            for link_element in link_elements:
                href = link_element['href']
                if href.startswith('/'):
                    full_url = f"{host_page}{href}"
                    file_links.append(full_url)
                    self.logger.debug(f"找到文件链接: {full_url}")
            
            self.logger.info(f"从相册中提取到 {len(file_links)} 个文件链接")
            return file_links
            
        except Exception as e:
            self.logger.error(f"提取相册链接失败: {e}")
            return []
    
    def get_identifier(self, url: str, soup: Optional[BeautifulSoup] = None) -> str:
        """
        从URL中提取标识符
        
        Args:
            url: bunkr URL
            soup: 可选的BeautifulSoup对象
            
        Returns:
            标识符字符串
        """
        decoded_url = unquote(url)
        
        try:
            url_type = self.get_url_type(decoded_url)
            if url_type == 'album':
                return self.get_album_id(decoded_url)
            else:
                return self.get_media_slug(decoded_url, soup)
        except IndexError:
            self.logger.error("提取标识符时出错")
            return url.split('/')[-1] or "unknown"
    
    def get_album_id(self, url: str) -> str:
        """从URL中提取相册ID"""
        try:
            return url.rstrip('/').split("/")[-1]
        except IndexError:
            self.logger.error("无效的URL格式")
            return "unknown"
    
    def get_media_slug(self, url: str, soup: Optional[BeautifulSoup]) -> str:
        """
        提取媒体slug
        
        Args:
            url: 媒体URL
            soup: HTML soup对象
            
        Returns:
            媒体slug
        """
        media_slug = url.rstrip("/").split("/")[-1]
        if re.fullmatch(BunkrConfig.VALID_SLUG_REGEX, media_slug):
            return media_slug
        
        # 回退：从script标签中查找slug
        if soup:
            for item in soup.find_all("script"):
                script_text = item.get_text()
                match = re.search(BunkrConfig.MEDIA_SLUG_REGEX, script_text)
                if match:
                    return match.group(1)
        
        self.logger.warning("无法在HTML内容中找到媒体slug")
        return media_slug or "unknown"
    
    def get_album_name(self, soup: BeautifulSoup) -> Optional[str]:
        """从页面HTML中提取相册名称"""
        name_container = soup.find(
            "div",
            {"class": "text-subs font-semibold flex text-base sm:text-lg"},
        )
        
        if name_container:
            h1_tag = name_container.find("h1")
            if h1_tag:
                album_name = h1_tag.get_text(strip=True)
                return html.unescape(album_name)
        
        return None
    
    def get_item_filename(self, soup: BeautifulSoup) -> str:
        """从HTML中提取文件名"""
        filename_container = soup.find(
            "h1",
            {"class": "text-subs font-semibold text-base sm:text-lg truncate"},
        )
        
        if filename_container:
            filename = filename_container.get_text(strip=True)
            return filename.encode("latin1").decode("utf-8")
        
        return "unknown_file"
    
    def get_api_response(self, item_url: str, soup: Optional[BeautifulSoup] = None) -> Optional[Dict[str, Any]]:
        """
        从Bunkr API获取加密数据
        
        Args:
            item_url: 项目URL
            soup: 可选的BeautifulSoup对象
            
        Returns:
            API响应数据
        """
        slug = self.get_identifier(item_url, soup)
        
        try:
            response = self.session.post(BunkrConfig.BUNKR_API, json={"slug": slug}, timeout=15)
            if response.status_code != BunkrConfig.HTTP_STATUS_OK:
                self.logger.warning(f"获取slug '{slug}' 的加密数据失败")
                return None
            
            return response.json()
            
        except requests.RequestException as e:
            self.logger.error(f"请求slug '{slug}' 的加密数据时出错: {e}")
            return None
    
    def decrypt_url(self, api_response: Dict[str, Any]) -> str:
        """
        使用基于时间戳的密钥解密URL
        
        Args:
            api_response: API响应数据
            
        Returns:
            解密后的URL
        """
        try:
            timestamp = api_response["timestamp"]
            encrypted_bytes = base64.b64decode(api_response["url"])
        except KeyError as e:
            self.logger.error(f"缺少必需的加密数据字段: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"解码加密数据失败: {e}")
            return ""
        
        # 基于时间戳生成密钥
        time_key = floor(timestamp / 3600)
        secret_key = f"SECRET_KEY_{time_key}"
        
        # 创建密钥的循环迭代器
        secret_key_bytes = secret_key.encode("utf-8")
        cycled_key = cycle(secret_key_bytes)
        
        # 解密数据
        try:
            decrypted_bytes = bytearray(byte ^ next(cycled_key) for byte in encrypted_bytes)
            decrypted_url = decrypted_bytes.decode("utf-8", errors="ignore")
            
            self.logger.debug(f"成功解密URL: {decrypted_url[:50]}...")
            return decrypted_url
            
        except Exception as e:
            self.logger.error(f"URL解密失败: {e}")
            return ""
    
    def get_url_based_filename(self, download_link: str) -> str:
        """从下载链接中提取文件名"""
        parsed_url = urlparse(download_link)
        return parsed_url.path.split("/")[-1]
    
    def format_item_filename(self, original_filename: str, url_based_filename: str) -> str:
        """
        合并两个文件名，保留第一个文件名的扩展名
        
        Args:
            original_filename: 原始文件名
            url_based_filename: 基于URL的文件名
            
        Returns:
            格式化后的文件名
        """
        if original_filename == url_based_filename:
            return original_filename
        
        # 提取基本名称（不含扩展名）和扩展名
        original_base = Path(original_filename).stem
        extension = Path(original_filename).suffix
        url_base = Path(url_based_filename).stem
        
        if original_base in url_base:
            return url_based_filename
        
        # 用连字符组合基本名称并添加扩展名
        return f"{original_base}-{url_base}{extension}"
    
    def get_chunk_size(self, file_size: int) -> int:
        """根据文件大小确定最优块大小"""
        for threshold, chunk_size in BunkrConfig.THRESHOLDS:
            if file_size < threshold:
                return chunk_size
        
        return BunkrConfig.LARGE_FILE_CHUNK_SIZE
    
    def download_file_with_progress(self, url: str, file_path: Path, max_retries: int = BunkrConfig.MAX_RETRIES) -> bool:
        """
        带进度显示和重试机制的文件下载
        
        Args:
            url: 下载URL
            file_path: 文件保存路径
            max_retries: 最大重试次数
            
        Returns:
            True表示下载成功
        """
        for attempt in range(max_retries):
            try:
                # 检查子域名是否离线
                if self.status_manager.subdomain_is_offline(url):
                    if attempt == max_retries - 1:
                        self.logger.warning(f"子域名可能离线: {file_path.name}")
                        return False
                    continue
                
                if attempt == 0:
                    self.logger.info(f"正在下载文件: {file_path.name}")
                else:
                    self.logger.info(f"正在下载文件 (重试 {attempt}/{max_retries-1}): {file_path.name}")
                
                response = self.session.get(
                    url,
                    stream=True,
                    headers=BunkrConfig.DOWNLOAD_HEADERS,
                    timeout=30
                )
                response.raise_for_status()
                
                # 获取文件大小
                file_size = int(response.headers.get('Content-Length', -1))
                if file_size == -1:
                    self.logger.warning("响应头中未提供Content-Length")
                
                # 创建临时文件
                temp_file_path = file_path.with_suffix('.temp')
                
                chunk_size = self.get_chunk_size(file_size)
                total_downloaded = 0
                
                with open(temp_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            total_downloaded += len(chunk)
                            
                            # 显示下载进度
                            if file_size > 0 and total_downloaded % (chunk_size * 100) == 0:
                                progress = (total_downloaded / file_size) * 100
                                self.logger.info(f"下载进度: {progress:.1f}% ({total_downloaded}/{file_size})")
                
                # 下载完成后重命名文件
                if file_size > 0 and total_downloaded == file_size:
                    temp_file_path.rename(file_path)
                    self.logger.info(f"文件下载完成: {file_path}")
                    return True
                elif file_size <= 0:
                    # 未知文件大小的情况下，假设下载完成
                    temp_file_path.rename(file_path)
                    self.logger.info(f"文件下载完成: {file_path}")
                    return True
                else:
                    # 下载不完整，保留.temp扩展名
                    self.logger.warning(f"文件下载不完整: {file_path.name}")
                    return False
                
            except requests.exceptions.RequestException as e:
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    
                    if status_code == BunkrConfig.HTTP_STATUS_SERVER_DOWN:
                        # 标记子域名为离线
                        marked_subdomain = self.status_manager.mark_subdomain_as_offline(url)
                        self.logger.warning(f"服务器无响应，已标记子域名 {marked_subdomain} 为离线")
                        break
                    
                    if status_code in (429, 503):
                        if attempt == 0:
                            self.logger.warning(f"请求过多，准备重试...")
                        else:
                            self.logger.warning(f"请求过多，重试中... ({attempt}/{max_retries-1})")
                        if attempt < max_retries - 1:
                            delay = 3 ** (attempt + 1) + random.uniform(1, 3)
                            time.sleep(delay)
                            continue
                    
                    if status_code == BunkrConfig.HTTP_STATUS_BAD_GATEWAY:
                        self.logger.error(f"服务器错误（Bad Gateway）: {file_path.name}")
                        break
                
                if attempt == 0:
                    self.logger.error(f"下载请求失败: {e}")
                else:
                    self.logger.error(f"下载请求失败 (重试 {attempt}/{max_retries-1}): {e}")
                
                if attempt < max_retries - 1:
                    delay = 2 ** attempt + random.uniform(1, 2)
                    time.sleep(delay)
                else:
                    break
            
            except Exception as e:
                self.logger.error(f"下载过程中发生未知错误: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    break
        
        return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除不安全字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            安全的文件名
        """
        # 移除不安全字符
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # 限制长度
        if len(safe_filename) > BunkrConfig.MAX_FILENAME_LEN:
            name, ext = os.path.splitext(safe_filename)
            safe_filename = name[:BunkrConfig.MAX_FILENAME_LEN-len(ext)] + ext
        
        return safe_filename
    
    async def get_download_info_async(self, item_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        异步获取下载信息（链接和文件名）
        
        Args:
            item_url: 项目URL
            
        Returns:
            (下载链接, 文件名) 元组
        """
        try:
            # 获取页面内容
            async with aiohttp.ClientSession(headers=BunkrConfig.HEADERS) as session:
                async with session.get(item_url, timeout=15) as response:
                    if response.status != 200:
                        self.logger.error(f"获取页面失败: {item_url}")
                        return None, None
                    
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, 'html.parser')
            
            # 获取API响应
            api_response = self.get_api_response(item_url, soup)
            if not api_response:
                return None, None
            
            # 解密URL
            download_link = self.decrypt_url(api_response)
            if not download_link:
                return None, None
            
            # 获取文件名
            item_filename = self.get_item_filename(soup)
            url_based_filename = self.get_url_based_filename(download_link) if download_link else None
            
            if url_based_filename:
                formatted_filename = self.format_item_filename(item_filename, url_based_filename)
            else:
                formatted_filename = item_filename
            
            return download_link, formatted_filename
            
        except Exception as e:
            self.logger.error(f"异步获取下载信息失败: {e}")
            return None, None
    
    def get_download_info(self, item_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        同步获取下载信息（链接和文件名）
        
        Args:
            item_url: 项目URL
            
        Returns:
            (下载链接, 文件名) 元组
        """
        try:
            # 获取页面内容
            response = self.session.get(item_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 获取API响应
            api_response = self.get_api_response(item_url, soup)
            if not api_response:
                return None, None
            
            # 解密URL
            download_link = self.decrypt_url(api_response)
            if not download_link:
                return None, None
            
            # 获取文件名
            item_filename = self.get_item_filename(soup)
            url_based_filename = self.get_url_based_filename(download_link) if download_link else None
            
            if url_based_filename:
                formatted_filename = self.format_item_filename(item_filename, url_based_filename)
            else:
                formatted_filename = item_filename
            
            return download_link, formatted_filename
            
        except Exception as e:
            self.logger.error(f"获取下载信息失败: {e}")
            return None, None
    
    def download_from_url(self, url: str, ignore_patterns: Optional[List[str]] = None, include_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        从bunkr URL下载文件（主入口方法）
        
        Args:
            url: bunkr URL
            ignore_patterns: 忽略的文件名模式列表
            include_patterns: 包含的文件名模式列表
            
        Returns:
            下载结果字典
        """
        result = {
            'success': False,
            'url': url,
            'type': None,
            'files_downloaded': 0,
            'files_failed': 0,
            'downloaded_files': [],
            'skipped_files': [],
            'failed_files': [],
            'error': None
        }
        
        try:
            # 验证是否为bunkr URL
            if not self.is_bunkr_url(url):
                result['error'] = f"不是有效的bunkr URL: {url}"
                return result
            
            # 判断URL类型
            url_type = self.get_url_type(url)
            result['type'] = url_type
            
            if url_type == 'album':
                # 处理相册类型
                file_links = self.extract_file_links_from_album(url)
                
                if not file_links:
                    result['error'] = "未能从相册中提取到文件链接"
                    return result
                
                # 逐个下载文件
                for file_link in file_links:
                    try:
                        file_result = self._download_single_file(
                            file_link, 
                            ignore_patterns, 
                            include_patterns
                        )
                        
                        if file_result['success']:
                            result['files_downloaded'] += 1
                            result['downloaded_files'].extend(file_result['downloaded_files'])
                        elif file_result.get('skipped'):
                            result['skipped_files'].append(file_result.get('filename', 'unknown'))
                        else:
                            result['files_failed'] += 1
                            result['failed_files'].append(file_result.get('filename', 'unknown'))
                            self.logger.warning(f"单个文件下载失败: {file_link}")
                        
                        # 添加延迟避免请求过快
                        time.sleep(random.uniform(0.5, 2.0))
                        
                    except Exception as e:
                        self.logger.error(f"处理文件链接时出错 {file_link}: {e}")
                        result['files_failed'] += 1
                
                result['success'] = result['files_downloaded'] > 0
                
            elif url_type in ['file', 'video']:
                # 处理单个文件
                file_result = self._download_single_file(url, ignore_patterns, include_patterns)
                result.update(file_result)
                if result['success']:
                    result['files_downloaded'] = 1
                elif file_result.get('skipped'):
                    result['skipped_files'].append(file_result.get('filename', 'unknown'))
                else:
                    result['files_failed'] = 1
                    result['failed_files'].append(file_result.get('filename', 'unknown'))
            
            else:
                result['error'] = f"不支持的URL类型: {url}"
                return result
            
            # 输出总结信息
            self.logger.info(f"下载完成 - 成功: {result['files_downloaded']}, 失败: {result['files_failed']}, 跳过: {len(result['skipped_files'])}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"下载过程中发生错误: {e}")
            result['error'] = str(e)
            return result
    
    def _should_skip_file(self, filename: str, ignore_patterns: Optional[List[str]] = None, include_patterns: Optional[List[str]] = None) -> bool:
        """
        判断是否应该跳过文件下载
        
        Args:
            filename: 文件名
            ignore_patterns: 忽略模式列表
            include_patterns: 包含模式列表
            
        Returns:
            True表示应该跳过
        """
        # 检查忽略模式
        if ignore_patterns:
            for pattern in ignore_patterns:
                if pattern in filename:
                    self.logger.info(f"文件 {filename} 匹配忽略模式 '{pattern}'，跳过下载")
                    return True
        
        # 检查包含模式
        if include_patterns:
            for pattern in include_patterns:
                if pattern in filename:
                    return False
            self.logger.info(f"文件 {filename} 不匹配任何包含模式，跳过下载")
            return True
        
        return False
    
    def _download_single_file(self, file_url: str, ignore_patterns: Optional[List[str]] = None, include_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        下载单个文件的内部方法
        
        Args:
            file_url: 文件页面URL
            ignore_patterns: 忽略模式列表
            include_patterns: 包含模式列表
            
        Returns:
            下载结果字典
        """
        result = {
            'success': False,
            'skipped': False,
            'file_url': file_url,
            'filename': None,
            'downloaded_files': [],
            'error': None
        }
        
        try:
            # 获取下载信息
            download_link, filename = self.get_download_info(file_url)
            result['filename'] = filename
            
            if not download_link or not filename:
                result['error'] = "获取下载信息失败"
                return result
            
            # 清理文件名
            safe_filename = self._sanitize_filename(filename)
            file_path = self.download_dir / safe_filename
            
            # 检查文件是否已存在
            if file_path.exists():
                self.logger.info(f"文件已存在，跳过下载: {safe_filename}")
                result['skipped'] = True
                return result
            
            # 检查是否应该跳过文件
            if self._should_skip_file(safe_filename, ignore_patterns, include_patterns):
                result['skipped'] = True
                return result
            
            # 下载文件
            if self.download_file_with_progress(download_link, file_path):
                result['success'] = True
                result['downloaded_files'].append(safe_filename)
            else:
                result['error'] = "文件下载失败"
            
            return result
            
        except Exception as e:
            self.logger.error(f"单个文件下载过程中发生错误: {e}")
            result['error'] = str(e)
            return result
    
    async def download_from_url_async(self, url: str, ignore_patterns: Optional[List[str]] = None, include_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        异步版本的URL下载方法
        
        Args:
            url: bunkr URL
            ignore_patterns: 忽略模式列表
            include_patterns: 包含模式列表
            
        Returns:
            下载结果字典
        """
        result = {
            'success': False,
            'url': url,
            'type': None,
            'files_downloaded': 0,
            'files_failed': 0,
            'downloaded_files': [],
            'skipped_files': [],
            'failed_files': [],
            'error': None
        }
        
        try:
            # 验证是否为bunkr URL
            if not self.is_bunkr_url(url):
                result['error'] = f"不是有效的bunkr URL: {url}"
                return result
            
            # 判断URL类型
            url_type = self.get_url_type(url)
            result['type'] = url_type
            
            if url_type == 'album':
                # 处理相册类型
                file_links = self.extract_file_links_from_album(url)
                
                if not file_links:
                    result['error'] = "未能从相册中提取到文件链接"
                    return result
                
                # 创建异步任务
                tasks = []
                for file_link in file_links:
                    task = asyncio.create_task(
                        self._download_single_file_async(file_link, ignore_patterns, include_patterns)
                    )
                    tasks.append(task)
                
                # 等待所有任务完成
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for file_result in results:
                    if isinstance(file_result, Exception):
                        self.logger.error(f"异步下载任务失败: {file_result}")
                        result['files_failed'] += 1
                        continue
                    
                    if file_result['success']:
                        result['files_downloaded'] += 1
                        result['downloaded_files'].extend(file_result['downloaded_files'])
                    elif file_result.get('skipped'):
                        result['skipped_files'].append(file_result.get('filename', 'unknown'))
                    else:
                        result['files_failed'] += 1
                        result['failed_files'].append(file_result.get('filename', 'unknown'))
                
                result['success'] = result['files_downloaded'] > 0
                
            elif url_type in ['file', 'video']:
                # 处理单个文件
                file_result = await self._download_single_file_async(url, ignore_patterns, include_patterns)
                result.update(file_result)
                if result['success']:
                    result['files_downloaded'] = 1
                elif file_result.get('skipped'):
                    result['skipped_files'].append(file_result.get('filename', 'unknown'))
                else:
                    result['files_failed'] = 1
                    result['failed_files'].append(file_result.get('filename', 'unknown'))
            
            else:
                result['error'] = f"不支持的URL类型: {url}"
                return result
            
            # 输出总结信息
            self.logger.info(f"异步下载完成 - 成功: {result['files_downloaded']}, 失败: {result['files_failed']}, 跳过: {len(result['skipped_files'])}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"异步下载过程中发生错误: {e}")
            result['error'] = str(e)
            return result
    
    async def _download_single_file_async(self, file_url: str, ignore_patterns: Optional[List[str]] = None, include_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        异步版本的单个文件下载方法
        
        Args:
            file_url: 文件页面URL
            ignore_patterns: 忽略模式列表
            include_patterns: 包含模式列表
            
        Returns:
            下载结果字典
        """
        result = {
            'success': False,
            'skipped': False,
            'file_url': file_url,
            'filename': None,
            'downloaded_files': [],
            'error': None
        }
        
        try:
            # 获取下载信息
            download_link, filename = await self.get_download_info_async(file_url)
            result['filename'] = filename
            
            if not download_link or not filename:
                result['error'] = "获取下载信息失败"
                return result
            
            # 清理文件名
            safe_filename = self._sanitize_filename(filename)
            file_path = self.download_dir / safe_filename
            
            # 检查文件是否已存在
            if file_path.exists():
                self.logger.info(f"文件已存在，跳过下载: {safe_filename}")
                result['skipped'] = True
                return result
            
            # 检查是否应该跳过文件
            if self._should_skip_file(safe_filename, ignore_patterns, include_patterns):
                result['skipped'] = True
                return result
            
            # 异步下载文件
            if await self._download_file_async(download_link, file_path):
                result['success'] = True
                result['downloaded_files'].append(safe_filename)
            else:
                result['error'] = "异步文件下载失败"
            
            return result
            
        except Exception as e:
            self.logger.error(f"异步单个文件下载过程中发生错误: {e}")
            result['error'] = str(e)
            return result
    
    async def _download_file_async(self, url: str, file_path: Path, max_retries: int = BunkrConfig.MAX_RETRIES) -> bool:
        """
        异步文件下载方法
        
        Args:
            url: 下载URL
            file_path: 文件保存路径
            max_retries: 最大重试次数
            
        Returns:
            True表示下载成功
        """
        for attempt in range(max_retries):
            try:
                # 检查子域名是否离线
                if self.status_manager.subdomain_is_offline(url):
                    if attempt == max_retries - 1:
                        self.logger.warning(f"子域名可能离线: {file_path.name}")
                        return False
                    continue
                
                if attempt == 0:
                    self.logger.info(f"正在异步下载文件: {file_path.name}")
                else:
                    self.logger.info(f"正在异步下载文件 (重试 {attempt}/{max_retries-1}): {file_path.name}")
                
                async with aiohttp.ClientSession(headers=BunkrConfig.DOWNLOAD_HEADERS) as session:
                    async with session.get(url, timeout=30) as response:
                        if response.status != 200:
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=response.status
                            )
                        
                        # 获取文件大小
                        file_size = int(response.headers.get('Content-Length', -1))
                        if file_size == -1:
                            self.logger.warning("响应头中未提供Content-Length")
                        
                        # 创建临时文件
                        temp_file_path = file_path.with_suffix('.temp')
                        
                        chunk_size = self.get_chunk_size(file_size)
                        total_downloaded = 0
                        
                        with open(temp_file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(chunk_size):
                                if chunk:
                                    f.write(chunk)
                                    total_downloaded += len(chunk)
                                    
                                    # 显示下载进度
                                    if file_size > 0 and total_downloaded % (chunk_size * 100) == 0:
                                        progress = (total_downloaded / file_size) * 100
                                        self.logger.info(f"异步下载进度: {progress:.1f}% ({total_downloaded}/{file_size})")
                        
                        # 下载完成后重命名文件
                        if file_size > 0 and total_downloaded == file_size:
                            temp_file_path.rename(file_path)
                            self.logger.info(f"异步文件下载完成: {file_path}")
                            return True
                        elif file_size <= 0:
                            # 未知文件大小的情况下，假设下载完成
                            temp_file_path.rename(file_path)
                            self.logger.info(f"异步文件下载完成: {file_path}")
                            return True
                        else:
                            # 下载不完整，保留.temp扩展名
                            self.logger.warning(f"异步文件下载不完整: {file_path.name}")
                            return False
            
            except aiohttp.ClientError as e:
                if hasattr(e, 'status'):
                    status_code = e.status
                    
                    if status_code == BunkrConfig.HTTP_STATUS_SERVER_DOWN:
                        # 标记子域名为离线
                        marked_subdomain = self.status_manager.mark_subdomain_as_offline(url)
                        self.logger.warning(f"服务器无响应，已标记子域名 {marked_subdomain} 为离线")
                        break
                    
                    if status_code in (429, 503):
                        if attempt == 0:
                            self.logger.warning(f"请求过多，准备重试...")
                        else:
                            self.logger.warning(f"请求过多，重试中... ({attempt}/{max_retries-1})")
                        if attempt < max_retries - 1:
                            delay = 3 ** (attempt + 1) + random.uniform(1, 3)
                            await asyncio.sleep(delay)
                            continue
                    
                    if status_code == BunkrConfig.HTTP_STATUS_BAD_GATEWAY:
                        self.logger.error(f"服务器错误（Bad Gateway）: {file_path.name}")
                        break
                
                if attempt == 0:
                    self.logger.error(f"异步下载请求失败: {e}")
                else:
                    self.logger.error(f"异步下载请求失败 (重试 {attempt}/{max_retries-1}): {e}")
                
                if attempt < max_retries - 1:
                    delay = 2 ** attempt + random.uniform(1, 2)
                    await asyncio.sleep(delay)
                else:
                    break
            
            except Exception as e:
                self.logger.error(f"异步下载过程中发生未知错误: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    break
        
        return False


# 便捷函数
def download_from_bunkr(url: str, download_dir: str = "downloads", ignore_patterns: Optional[List[str]] = None, include_patterns: Optional[List[str]] = None, use_async: bool = False) -> Dict[str, Any]:
    """
    便捷函数：从bunkr URL下载文件
    
    Args:
        url: bunkr URL
        download_dir: 下载目录
        ignore_patterns: 忽略的文件名模式列表
        include_patterns: 包含的文件名模式列表
        use_async: 是否使用异步下载
        
    Returns:
        下载结果字典
    """
    downloader = BunkrDownloader(download_dir=download_dir)
    
    if use_async:
        return asyncio.run(downloader.download_from_url_async(url, ignore_patterns, include_patterns))
    else:
        return downloader.download_from_url(url, ignore_patterns, include_patterns)


async def download_from_bunkr_async(url: str, download_dir: str = "downloads", ignore_patterns: Optional[List[str]] = None, include_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    异步便捷函数：从bunkr URL下载文件
    
    Args:
        url: bunkr URL
        download_dir: 下载目录
        ignore_patterns: 忽略的文件名模式列表
        include_patterns: 包含的文件名模式列表
        
    Returns:
        下载结果字典
    """
    downloader = BunkrDownloader(download_dir=download_dir)
    return await downloader.download_from_url_async(url, ignore_patterns, include_patterns)



import json
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class Cookie:
    """单个cookie的数据结构"""
    domain: str
    name: str
    value: str
    path: str = "/"
    expirationDate: Optional[float] = None
    hostOnly: bool = False
    httpOnly: bool = False
    sameSite: str = "unspecified"
    secure: bool = False
    session: bool = True
    storeId: str = "0"
    
    def is_expired(self) -> bool:
        """检查cookie是否已过期"""
        if self.session or self.expirationDate is None:
            return False
        return time.time() > self.expirationDate
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = asdict(self)
        if self.expirationDate is None:
            result.pop('expirationDate', None)
        return result


class BrowserCookies:
    """
    浏览器格式cookies管理类，支持初始化、读取、保存和使用cookies
    处理包含完整cookie属性的浏览器格式
    """
    
    def __init__(self, file_path: Optional[str] = None):
        """
        初始化cookies类
        
        Args:
            file_path: cookies文件路径，默认为当前目录下的browser_cookies.json
        """
        if file_path is None:
            file_path = "browser_cookies.json"
        
        self.file_path = Path(file_path)
        self._cookies: List[Cookie] = []
        self.load()
    
    def load(self) -> None:
        """从文件加载cookies"""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    cookies_data = json.load(f)
                
                self._cookies = []
                for cookie_data in cookies_data:
                    # 处理可能缺失的字段
                    if 'expirationDate' in cookie_data and cookie_data['expirationDate'] is None:
                        cookie_data.pop('expirationDate')
                    
                    cookie = Cookie(**cookie_data)
                    self._cookies.append(cookie)
                
                print(f"已从 {self.file_path} 加载 {len(self._cookies)} 个cookies")
            else:
                print(f"cookies文件 {self.file_path} 不存在，将创建新文件")
        except Exception as e:
            print(f"加载cookies时出错: {e}")
            self._cookies = []
    
    def save(self) -> None:
        """保存cookies到文件"""
        try:
            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 过滤掉过期的cookies
            valid_cookies = [cookie for cookie in self._cookies if not cookie.is_expired()]
            
            cookies_data = [cookie.to_dict() for cookie in valid_cookies]
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_data, f, ensure_ascii=False, indent=2)
            
            print(f"已保存 {len(valid_cookies)} 个有效cookies到 {self.file_path}")
        except Exception as e:
            print(f"保存cookies时出错: {e}")
    
    def add_cookie(self, cookie: Cookie) -> None:
        """
        添加一个cookie
        
        Args:
            cookie: Cookie对象
        """
        # 检查是否已存在相同的cookie（相同域名、名称、路径）
        existing_index = self._find_cookie_index(cookie.domain, cookie.name, cookie.path)
        
        if existing_index is not None:
            # 更新现有cookie
            self._cookies[existing_index] = cookie
            print(f"已更新cookie: {cookie.name} (domain: {cookie.domain})")
        else:
            # 添加新cookie
            self._cookies.append(cookie)
            print(f"已添加cookie: {cookie.name} (domain: {cookie.domain})")
    
    def add_cookies_from_dict(self, cookies_data: List[Dict[str, Any]]) -> None:
        """
        从字典列表批量添加cookies
        
        Args:
            cookies_data: cookie字典列表
        """
        for cookie_data in cookies_data:
            try:
                # 处理可能缺失的字段
                if 'expirationDate' in cookie_data and cookie_data['expirationDate'] is None:
                    cookie_data.pop('expirationDate')
                
                cookie = Cookie(**cookie_data)
                self.add_cookie(cookie)
            except Exception as e:
                print(f"添加cookie时出错: {e}, 数据: {cookie_data}")
    
    def get_cookie(self, name: str, domain: Optional[str] = None, path: str = "/") -> Optional[Cookie]:
        """
        获取指定cookie
        
        Args:
            name: cookie名称
            domain: cookie域名（可选）
            path: cookie路径
            
        Returns:
            Cookie对象或None
        """
        for cookie in self._cookies:
            if (cookie.name == name and 
                cookie.path == path and 
                (domain is None or cookie.domain == domain) and
                not cookie.is_expired()):
                return cookie
        return None
    
    def get_cookies_by_domain(self, domain: str) -> List[Cookie]:
        """
        获取指定域名的所有cookies
        
        Args:
            domain: 域名
            
        Returns:
            Cookie对象列表
        """
        return [cookie for cookie in self._cookies 
                if cookie.domain == domain and not cookie.is_expired()]
    
    def get_cookie_value(self, name: str, domain: Optional[str] = None, path: str = "/") -> Optional[str]:
        """
        获取cookie值
        
        Args:
            name: cookie名称
            domain: cookie域名（可选）
            path: cookie路径
            
        Returns:
            cookie值或None
        """
        cookie = self.get_cookie(name, domain, path)
        return cookie.value if cookie else None
    
    def delete_cookie(self, name: str, domain: Optional[str] = None, path: str = "/") -> bool:
        """
        删除cookie
        
        Args:
            name: cookie名称
            domain: cookie域名（可选）
            path: cookie路径
            
        Returns:
            是否成功删除
        """
        index = self._find_cookie_index(domain or "", name, path)
        if index is not None:
            deleted_cookie = self._cookies.pop(index)
            print(f"已删除cookie: {deleted_cookie.name} (domain: {deleted_cookie.domain})")
            return True
        else:
            print(f"未找到cookie: {name} (domain: {domain}, path: {path})")
            return False
    
    def clear_expired(self) -> int:
        """
        清除过期的cookies
        
        Returns:
            清除的cookie数量
        """
        original_count = len(self._cookies)
        self._cookies = [cookie for cookie in self._cookies if not cookie.is_expired()]
        cleared_count = original_count - len(self._cookies)
        if cleared_count > 0:
            print(f"已清除 {cleared_count} 个过期cookies")
        return cleared_count
    
    def clear_all(self) -> None:
        """清空所有cookies"""
        self._cookies.clear()
        print("已清空所有cookies")
    
    def get_primary_domain(self) -> Optional[str]:
        """
        自动推断主域名（不包含子域名的根域名）
        优先选择simpcity相关域名，然后选择cookie数量最多的域名
        
        Returns:
            推断出的主域名，如果没有有效cookies则返回None
        """
        domain_counts = {}
        simpcity_domains = []
        
        for cookie in self._cookies:
            if not cookie.is_expired():
                domain = cookie.domain
                # 移除域名前的点号
                clean_domain = domain.lstrip('.')
                
                # 统计各域名的cookie数量
                domain_counts[clean_domain] = domain_counts.get(clean_domain, 0) + 1
                
                # 收集simpcity相关域名
                if 'simpcity' in clean_domain.lower():
                    if clean_domain not in simpcity_domains:
                        simpcity_domains.append(clean_domain)
        
        if not domain_counts:
            return None
        
        # 优先返回simpcity相关域名
        if simpcity_domains:
            # 返回cookie数量最多的simpcity域名
            return max(simpcity_domains, key=lambda d: domain_counts.get(d, 0))
        
        # 否则返回cookie数量最多的域名
        return max(domain_counts.keys(), key=lambda d: domain_counts[d])
    
    def to_requests_cookies(self, domain: Optional[str] = None) -> Dict[str, str]:
        """
        转换为requests库可用的cookies格式
        
        Args:
            domain: 指定域名，如果为None则包含所有域名的cookies
            
        Returns:
            requests格式的cookies字典
        """
        cookies_dict = {}
        for cookie in self._cookies:
            if not cookie.is_expired():
                if domain is None or cookie.domain == domain or cookie.domain == f".{domain}":
                    cookies_dict[cookie.name] = cookie.value
        return cookies_dict
    
    def _find_cookie_index(self, domain: str, name: str, path: str) -> Optional[int]:
        """查找cookie在列表中的索引"""
        for i, cookie in enumerate(self._cookies):
            if (cookie.domain == domain and 
                cookie.name == name and 
                cookie.path == path):
                return i
        return None
    
    def __len__(self) -> int:
        """返回有效cookies数量"""
        return len([cookie for cookie in self._cookies if not cookie.is_expired()])
    
    def __str__(self) -> str:
        """返回cookies的字符串表示"""
        valid_count = len([cookie for cookie in self._cookies if not cookie.is_expired()])
        return f"BrowserCookies({valid_count} valid items, {len(self._cookies)} total)"
    
    def __repr__(self) -> str:
        """返回cookies的详细表示"""
        return f"BrowserCookies(file_path='{self.file_path}', items={len(self._cookies)})"


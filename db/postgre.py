import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any, List, Tuple
import logging
from contextlib import contextmanager
import os
import sys

from config.config import get_config


class PostgreSQLManager:
    """PostgreSQL数据库连接管理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化PostgreSQL连接管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = get_config(config_path)
        self.connection_pool = None
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
    def _setup_logging(self):
        """设置日志记录"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _get_db_config(self) -> Dict[str, Any]:
        """
        从配置文件中获取数据库配置
        
        Returns:
            数据库配置字典
        """
        db_config = self.config.get('database', {})
        print(db_config)
        
        # 如果配置文件中没有数据库配置，使用默认配置
        if not db_config:
            db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'database': os.getenv('DB_NAME', 'dionysus'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'password'),
                'min_connections': int(os.getenv('DB_MIN_CONNECTIONS', '1')),
                'max_connections': int(os.getenv('DB_MAX_CONNECTIONS', '20'))
            }
        
        return db_config
    
    def create_connection_pool(self) -> psycopg2.pool.ThreadedConnectionPool:
        """
        创建连接池
        
        Returns:
            连接池对象
        """
        if self.connection_pool is None:
            db_config = self._get_db_config()
            
            try:
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=db_config.get('min_connections', 1),
                    maxconn=db_config.get('max_connections', 20),
                    host=db_config['host'],
                    port=db_config['port'],
                    database=db_config['database'],
                    user=db_config['user'],
                    password=db_config['password']
                )
                self.logger.info("数据库连接池创建成功")
            except Exception as e:
                self.logger.error(f"创建数据库连接池失败: {e}")
                raise
        
        return self.connection_pool
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接上下文管理器
        
        Yields:
            数据库连接对象
        """
        if self.connection_pool is None:
            self.create_connection_pool()
        
        if self.connection_pool is None:
            raise RuntimeError("无法创建数据库连接池")
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"数据库连接错误: {e}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """
        获取数据库游标上下文管理器
        
        Args:
            cursor_factory: 游标工厂类
            
        Yields:
            数据库游标对象
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error(f"数据库操作错误: {e}")
                raise
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        执行查询语句
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """
        执行查询语句并返回单条结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            单条查询结果
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    
    def execute_insert(self, query: str, params: Optional[Tuple] = None) -> Optional[int]:
        """
        执行插入语句
        
        Args:
            query: SQL插入语句
            params: 插入参数
            
        Returns:
            新插入记录的ID（如果有）
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                result = cursor.fetchone()
                return result.get('id') if result else None
            return cursor.rowcount
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        执行更新语句
        
        Args:
            query: SQL更新语句
            params: 更新参数
            
        Returns:
            受影响的行数
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_delete(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        执行删除语句
        
        Args:
            query: SQL删除语句
            params: 删除参数
            
        Returns:
            受影响的行数
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        批量执行语句
        
        Args:
            query: SQL语句
            params_list: 参数列表
            
        Returns:
            受影响的行数
        """
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def close_all_connections(self):
        """关闭所有连接"""
        if self.connection_pool:
            self.connection_pool.closeall()
            self.connection_pool = None
            self.logger.info("所有数据库连接已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close_all_connections()

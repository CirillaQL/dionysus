#!/usr/bin/env python3
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

"""
SimpCity API 启动脚本

用于启动FastAPI服务器
"""

import sys
import os
import argparse
import uvicorn
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="启动SimpCity API服务")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="端口号 (默认: 8000)")
    parser.add_argument("--reload", action="store_true", help="启用自动重载 (开发模式)")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数 (默认: 1)")
    parser.add_argument("--log-level", default="info", 
                       choices=["critical", "error", "warning", "info", "debug"],
                       help="日志级别 (默认: info)")
    
    args = parser.parse_args()
    
    # 检查配置文件
    config_file = Path("config.yaml")
    if not config_file.exists():
        print("警告: config.yaml 不存在")
        print("请复制 config.yaml.example 为 config.yaml 并填写配置")
        
        example_config = Path("config.yaml.example")
        if example_config.exists():
            response = input("是否现在复制配置文件模板? (y/N): ")
            if response.lower() == 'y':
                import shutil
                shutil.copy(example_config, config_file)
                print(f"已复制 {example_config} 为 {config_file}")
                print("请编辑 config.yaml 文件，填写正确的配置信息")
                return
        else:
            print("错误: 配置文件模板不存在")
            return
    
    # 启动服务
    print(f"启动 SimpCity API 服务...")
    print(f"地址: http://{args.host}:{args.port}")
    print(f"文档: http://{args.host}:{args.port}/docs")
    print(f"日志级别: {args.log_level}")
    print(f"自动重载: {args.reload}")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,  # reload模式下只能用1个worker
            log_level=args.log_level,
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
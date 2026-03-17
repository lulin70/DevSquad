#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae Multi-Agent Dispatcher (包装脚本)

这个脚本是为了向后兼容，实际调用的是 trae_agent_dispatch_v2.py

使用方法:
    python3 trae_agent_dispatch.py --task "任务描述" --agent auto
"""

import sys
import os
from pathlib import Path

# 获取当前脚本目录
script_dir = Path(__file__).parent

# 导入 v2 版本的调度器
try:
    from trae_agent_dispatch_v2 import main
    if __name__ == "__main__":
        sys.exit(main())
except ImportError as e:
    print(f"❌ 错误：无法导入 trae_agent_dispatch_v2.py")
    print(f"详情：{e}")
    print(f"\n请确保以下文件存在：")
    print(f"  - {script_dir}/trae_agent_dispatch_v2.py")
    sys.exit(1)

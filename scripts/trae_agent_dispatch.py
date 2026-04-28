#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae Multi-Agent Dispatcher (包装脚本)

⚠️ 已弃用：此脚本为 V2 遗留，V3 请使用 `python3 scripts/cli.py dispatch` 或 `devsquad dispatch`

这个脚本是为了向后兼容，实际调用的是 trae_agent_dispatch_v2.py

使用方法:
    python3 trae_agent_dispatch.py --task "任务描述" --agent auto
    
注意：
    此脚本需要配置到 Trae 的 skill 系统中，通过 skills-index.json 的 triggers.manual.command 调用
"""

import sys
import os
from pathlib import Path

# 获取当前脚本目录（skill 的 scripts 目录）
script_dir = Path(__file__).parent.resolve()

# 将 skill 的 scripts 目录添加到 Python 路径
# 这样无论从哪个项目调用，都能正确导入 skill 的模块
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# 导入任务进度管理函数（供 trae_agent_dispatch_v2.py 使用）
try:
    from task_completion_checker import load_task_progress, update_task_status
except ImportError as e:
    # 如果无法导入，提供空实现以避免崩溃
    def load_task_progress(project_root):
        return {}
    
    def update_task_status(progress, task_id, status, description, project_root):
        pass

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

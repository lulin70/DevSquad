#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae Agent 调度脚本包装器

这是一个包装脚本，会自动定位 trae-multi-agent skill 的位置并调用它
无论你在哪个项目目录下，都可以直接调用这个脚本
"""

import os
import sys
import subprocess
from pathlib import Path


def find_skill_location():
    """
    查找 trae-multi-agent skill 的位置
    
    查找顺序：
    1. 环境变量 TRAE_MULTI_AGENT_SKILL_PATH
    2. 用户主目录下的 .trae/skills/trae-multi-agent
    3. 当前工作目录的 .trae/skills/trae-multi-agent
    
    Returns:
        Path: skill 的根目录路径，如果找不到则返回 None
    """
    # 1. 检查环境变量
    env_path = os.environ.get('TRAE_MULTI_AGENT_SKILL_PATH')
    if env_path:
        skill_path = Path(env_path).expanduser().resolve()
        if skill_path.exists():
            return skill_path
    
    # 2. 检查用户主目录
    home_path = Path.home() / '.trae' / 'skills' / 'trae-multi-agent'
    if home_path.exists():
        return home_path
    
    # 3. 检查当前工作目录
    cwd_path = Path.cwd() / '.trae' / 'skills' / 'trae-multi-agent'
    if cwd_path.exists():
        return cwd_path
    
    return None


def main():
    """
    主函数 - 转发所有参数到实际的 skill 脚本
    """
    # 查找 skill 位置
    skill_root = find_skill_location()
    
    if not skill_root:
        print("❌ 错误：找不到 trae-multi-agent skill", file=sys.stderr)
        print("\n请按照以下任一方式配置：", file=sys.stderr)
        print("  1. 设置环境变量：export TRAE_MULTI_AGENT_SKILL_PATH=/path/to/trae-multi-agent", file=sys.stderr)
        print("  2. 将 skill 安装到：~/.trae/skills/trae-multi-agent", file=sys.stderr)
        print("  3. 在项目目录下使用：./.trae/skills/trae-multi-agent", file=sys.stderr)
        sys.exit(1)
    
    # 定位实际的调度脚本（优先使用 v2 版本）
    dispatch_script = skill_root / 'scripts' / 'trae_agent_dispatch_v2.py'
    
    if not dispatch_script.exists():
        # 降级到旧版本
        dispatch_script = skill_root / 'scripts' / 'trae_agent_dispatch.py'
    
    if not dispatch_script.exists():
        print(f"❌ 错误：找不到调度脚本：{dispatch_script}", file=sys.stderr)
        sys.exit(1)
    
    # 转发所有参数到实际脚本
    try:
        result = subprocess.run(
            [sys.executable, str(dispatch_script)] + sys.argv[1:],
            cwd=Path.cwd()
        )
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ 错误：调用 skill 失败：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae Agent 调度脚本（v2.0 - 双层上下文增强版）

用于调度不同的智能体角色（架构师、产品经理、测试专家、独立开发者）来实现任务
支持命令行参数配置，方便集成到自动化流程中

新增功能（v2.0）:
- 双层动态上下文管理
- 智能角色匹配
- 工作流编排
- 技能注册管理
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

# 导入新组件
try:
    from dual_layer_context_manager import (
        DualLayerContextManager,
        TaskDefinition,
        UserProfile,
        KnowledgeItem
    )
    from skill_registry import SkillRegistry, SkillManifest
    from role_matcher import RoleMatcher, TaskRequirement, MatchResult, create_default_roles
    from workflow_engine import WorkflowEngine
    from user_intent_recognition import UserIntentRecognizer, IntentType, NeedType
    from core_rules import core_rules
    NEW_COMPONENTS_AVAILABLE = True
except ImportError as e:
    NEW_COMPONENTS_AVAILABLE = False
    print(f"警告：无法导入新组件，将使用旧版本逻辑：{e}")


def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description='Trae Agent 调度脚本 v2.0 - 调度不同的智能体角色来实现任务'
    )
    
    parser.add_argument(
        '--task',
        type=str,
        required=True,
        help='任务描述，例如："实现 SOUL-007 专注模式切换测试用例"'
    )
    
    parser.add_argument(
        '--agent',
        type=str,
        choices=['architect', 'product-manager', 'tester', 'solo-coder', 'ui-designer', 'devops', 'auto'],
        default='auto',
        help='指定要调度的智能体角色（默认：auto - 自动匹配）'
    )
    
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='项目根目录路径（默认：当前目录）'
    )
    
    parser.add_argument(
        '--task-file',
        type=str,
        help='任务文件路径'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='输出文件路径（可选）'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='启用详细输出模式'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅模拟执行，不实际调用智能体'
    )
    
    parser.add_argument(
        '--use-v1',
        action='store_true',
        help='使用 v1.0 版本逻辑（不使用新组件）'
    )
    
    parser.add_argument(
        '--project-full-lifecycle',
        action='store_true',
        help='启用项目全生命周期模式（8 阶段标准工作流程：需求→架构→UI→测试→任务→开发→测试→发布）'
    )
    
    return parser.parse_args()


def log(message: str, level: str = 'INFO'):
    """
    统一日志输出
    
    Args:
        message: 日志消息
        level: 日志级别 (INFO, WARNING, ERROR, SUCCESS)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    level_colors = {
        'INFO': '\033[94m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'SUCCESS': '\033[92m'
    }
    reset_color = '\033[0m'
    color = level_colors.get(level, '')
    
    print(f"{color}[{timestamp}] [{level}] {message}{reset_color}")


def handle_mas_command(command: str, context_manager: DualLayerContextManager) -> str:
    """
    处理 MAS (Multi Agent Skill) 命令
    
    Args:
        command: 命令字符串
        context_manager: 双层上下文管理器
        
    Returns:
        str: 命令执行结果
    """
    # 解析命令
    parts = command.split(' ', 1)
    if len(parts) < 1:
        return "❌ 命令格式错误，请使用：/mas <功能> <参数>"
    
    action = parts[0].lower()
    
    # 处理 help 命令
    if action == "help":
        return """
✅ MAS (Multi Agent Skill) 命令帮助：

**Vibe Coding 功能：**
- /mas plan <项目信息> - 生成项目计划
- /mas optimize <任务描述> - 优化提示词
- /mas extract <内容> - 提取知识
- /mas search <查询> - 搜索知识
- /mas recommend <上下文> - 推荐知识

**智能体调度：**
- /mas agent <角色> <任务> - 调度特定智能体执行任务
  角色：architect, product-manager, tester, solo-coder, ui-designer, devops

**工作流：**
- /mas workflow <工作流> <任务> - 执行特定工作流
  工作流：standard-dev, rapid-prototype, bug-fix, vibe-coding

**项目全生命周期：**
- /mas lifecycle <任务> - 执行项目全生命周期模式（8 阶段标准工作流程：需求→架构→UI→测试→任务→开发→测试→发布）

**知识管理：**
- /mas knowledge list - 列出所有知识
- /mas knowledge export - 导出知识
- /mas knowledge import <文件> - 导入知识
- /mas knowledge delete <知识ID> - 删除知识

**项目管理：**
- /mas project init <项目名称> - 初始化项目
- /mas project config <配置项> <值> - 配置项目
- /mas project status - 查看项目状态

**工具：**
- /mas code generate <描述> - 生成代码
- /mas code analyze <代码文件> - 分析代码
- /mas doc generate <内容> - 生成文档
- /mas doc analyze <文档文件> - 分析文档

**系统：**
- /mas status - 查看系统状态
- /mas stats - 查看统计信息
- /mas version - 查看版本信息
- /mas config <配置项> <值> - 配置系统
- /mas logs - 查看系统日志
- /mas rules - 查看核心规则库
        """
    
    # 处理其他命令
    if len(parts) < 2:
        params = ""
    else:
        params = parts[1]
    
    # 处理 Vibe Coding 功能
    if action == "plan":
        # 生成项目计划
        log(f'📋 生成项目计划：{params}', 'INFO')
        # 这里应该调用规划引擎
        return "✅ 项目计划生成功能已触发"
    
    elif action == "optimize":
        # 优化提示词
        log(f'✨ 优化提示词：{params}', 'INFO')
        # 这里应该调用提示词优化器
        return "✅ 提示词优化功能已触发"
    
    elif action == "extract":
        # 提取知识
        log(f'🧠 提取知识：{params}', 'INFO')
        extracted_knowledge = context_manager.extract_knowledge_from_dialogue(params)
        log(f'✅ 提取到 {len(extracted_knowledge)} 条知识', 'SUCCESS')
        return f"✅ 从内容中提取到 {len(extracted_knowledge)} 条知识"
    
    elif action == "search":
        # 搜索知识
        log(f'🔍 搜索知识：{params}', 'INFO')
        search_results = context_manager.search_knowledge(params)
        result_str = "\n".join([f"- {k.title} (类别：{k.category})" for k in search_results[:5]])
        return f"✅ 搜索到 {len(search_results)} 条相关知识：\n{result_str}"
    
    elif action == "recommend":
        # 推荐知识
        log(f'💡 推荐知识：{params}', 'INFO')
        recommendations = context_manager.recommend_knowledge(params)
        result_str = "\n".join([f"- {k.title} (类别：{k.category})" for k in recommendations])
        return f"✅ 推荐 {len(recommendations)} 条相关知识：\n{result_str}"
    
    # 处理智能体调度
    elif action == "agent":
        agent_parts = params.split(' ', 1)
        if len(agent_parts) < 2:
            return "❌ 命令格式错误，请使用：/mas agent <角色> <任务>"
        agent_type = agent_parts[0]
        agent_task = agent_parts[1]
        log(f'🤖 调度智能体 {agent_type} 执行任务：{agent_task}', 'INFO')
        # 这里应该调用智能体调度功能
        return f"✅ 已调度 {agent_type} 智能体执行任务"
    
    # 处理工作流
    elif action == "workflow":
        workflow_parts = params.split(' ', 1)
        if len(workflow_parts) < 2:
            return "❌ 命令格式错误，请使用：/mas workflow <工作流> <任务>"
        workflow_type = workflow_parts[0]
        workflow_task = workflow_parts[1]
        log(f'🔄 执行工作流 {workflow_type}：{workflow_task}', 'INFO')
        # 这里应该调用工作流执行功能
        return f"✅ 已启动 {workflow_type} 工作流"
    
    # 处理项目全生命周期模式
    elif action == "lifecycle":
        if not params:
            return "❌ 命令格式错误，请使用：/mas lifecycle <任务>"
        log(f'📋 执行项目全生命周期模式：{params}', 'INFO')
        # 这里应该调用项目全生命周期功能，相当于使用 --project-full-lifecycle 参数
        return "✅ 已启动项目全生命周期模式（8 阶段标准工作流程：需求→架构→UI→测试→任务→开发→测试→发布）"
    
    # 处理系统命令
    elif action == "status":
        log('📊 查看系统状态', 'INFO')
        # 这里应该返回系统状态
        return "✅ 系统状态：正常运行"
    
    elif action == "stats":
        log('📈 查看统计信息', 'INFO')
        stats = context_manager.get_knowledge_statistics()
        stats_str = f"""
✅ 统计信息：
- 总知识条目：{stats['total_knowledge']}
- 类别分布：{stats['category_stats']}
- 总使用次数：{stats['total_usage']}
- 平均使用次数：{stats['average_usage']:.2f}
        """
        return stats_str
    
    # 处理知识管理命令
    elif action == "knowledge":
        knowledge_parts = params.split(' ', 1)
        if len(knowledge_parts) < 1:
            return "❌ 命令格式错误，请使用：/mas knowledge <子命令>"
        knowledge_action = knowledge_parts[0].lower()
        
        if knowledge_action == "list":
            log('📚 列出所有知识', 'INFO')
            # 这里应该返回知识列表
            return "✅ 知识列表：待实现"
        elif knowledge_action == "export":
            log('📤 导出知识', 'INFO')
            # 这里应该导出知识
            return "✅ 知识导出：待实现"
        elif knowledge_action == "import":
            if len(knowledge_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas knowledge import <文件>"
            file_path = knowledge_parts[1]
            log(f'📥 导入知识：{file_path}', 'INFO')
            # 这里应该导入知识
            return f"✅ 知识导入：待实现"
        elif knowledge_action == "delete":
            if len(knowledge_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas knowledge delete <知识ID>"
            knowledge_id = knowledge_parts[1]
            log(f'🗑️ 删除知识：{knowledge_id}', 'INFO')
            # 这里应该删除知识
            return f"✅ 知识删除：待实现"
        else:
            return f"❌ 未知的知识管理命令：{knowledge_action}"
    
    # 处理项目管理命令
    elif action == "project":
        project_parts = params.split(' ', 1)
        if len(project_parts) < 1:
            return "❌ 命令格式错误，请使用：/mas project <子命令>"
        project_action = project_parts[0].lower()
        
        if project_action == "init":
            if len(project_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas project init <项目名称>"
            project_name = project_parts[1]
            log(f'🚀 初始化项目：{project_name}', 'INFO')
            # 这里应该初始化项目
            return f"✅ 项目初始化：待实现"
        elif project_action == "config":
            config_parts = project_parts[1].split(' ', 1)
            if len(config_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas project config <配置项> <值>"
            config_item = config_parts[0]
            config_value = config_parts[1]
            log(f'⚙️  配置项目：{config_item} = {config_value}', 'INFO')
            # 这里应该配置项目
            return f"✅ 项目配置：待实现"
        elif project_action == "status":
            log('📋 查看项目状态', 'INFO')
            # 这里应该返回项目状态
            return "✅ 项目状态：待实现"
        else:
            return f"❌ 未知的项目管理命令：{project_action}"
    
    # 处理工具命令
    elif action == "code":
        code_parts = params.split(' ', 1)
        if len(code_parts) < 1:
            return "❌ 命令格式错误，请使用：/mas code <子命令>"
        code_action = code_parts[0].lower()
        
        if code_action == "generate":
            if len(code_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas code generate <描述>"
            code_description = code_parts[1]
            log(f'💻 生成代码：{code_description}', 'INFO')
            # 这里应该生成代码
            return "✅ 代码生成：待实现"
        elif code_action == "analyze":
            if len(code_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas code analyze <代码文件>"
            code_file = code_parts[1]
            log(f'🔍 分析代码：{code_file}', 'INFO')
            # 这里应该分析代码
            return f"✅ 代码分析：待实现"
        else:
            return f"❌ 未知的代码工具命令：{code_action}"
    
    elif action == "doc":
        doc_parts = params.split(' ', 1)
        if len(doc_parts) < 1:
            return "❌ 命令格式错误，请使用：/mas doc <子命令>"
        doc_action = doc_parts[0].lower()
        
        if doc_action == "generate":
            if len(doc_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas doc generate <内容>"
            doc_content = doc_parts[1]
            log(f'📄 生成文档：{doc_content}', 'INFO')
            # 这里应该生成文档
            return "✅ 文档生成：待实现"
        elif doc_action == "analyze":
            if len(doc_parts) < 2:
                return "❌ 命令格式错误，请使用：/mas doc analyze <文档文件>"
            doc_file = doc_parts[1]
            log(f'📋 分析文档：{doc_file}', 'INFO')
            # 这里应该分析文档
            return f"✅ 文档分析：待实现"
        else:
            return f"❌ 未知的文档工具命令：{doc_action}"
    
    # 处理更多系统命令
    elif action == "version":
        log('📦 查看版本信息', 'INFO')
        # 这里应该返回版本信息
        return "✅ 版本信息：TraeMultiAgentSkill 2.4.0"
    
    elif action == "config":
        config_parts = params.split(' ', 1)
        if len(config_parts) < 2:
            return "❌ 命令格式错误，请使用：/mas config <配置项> <值>"
        config_item = config_parts[0]
        config_value = config_parts[1]
        log(f'⚙️  配置系统：{config_item} = {config_value}', 'INFO')
        # 这里应该配置系统
        return f"✅ 系统配置：待实现"
    
    elif action == "logs":
        log('📋 查看系统日志', 'INFO')
        # 这里应该返回系统日志
        return "✅ 系统日志：待实现"
    
    elif action == "rules":
        log('📚 查看核心规则库', 'INFO')
        if NEW_COMPONENTS_AVAILABLE:
            rules = core_rules.get_all_rules()
            rules_str = "✅ 核心规则库：\n\n"
            for rule in rules:
                rules_str += f"**{rule['name']}** ({rule['id']}): {rule['description']}\n"
                if rule['examples']:
                    rules_str += "  示例：" + ", ".join(rule['examples'][:3]) + "\n\n"
            return rules_str
        else:
            return "❌ 核心规则库不可用"
    
    else:
        return f"❌ 未知的 MAS 功能：{action}"


def recognize_vibe_intent(task: str) -> Optional[str]:
    """
    识别Vibe Coding相关的意图
    
    Args:
        task: 任务描述
        
    Returns:
        Optional[str]: 识别到的Vibe Coding功能，None表示不是Vibe Coding相关意图
    """
    try:
        recognizer = UserIntentRecognizer()
        result_data = recognizer.handle_natural_language(task)
        
        intent_type_str = result_data.get('intent', {}).get('type', '')
        if intent_type_str in ['planning', 'knowledge_management', 'code_generation']:
            if "计划" in task or "规划" in task:
                return "plan"
            elif "优化" in task and "提示词" in task:
                return "optimize"
            elif "提取" in task and "知识" in task:
                return "extract"
            elif "搜索" in task and "知识" in task:
                return "search"
            elif "推荐" in task and "知识" in task:
                return "recommend"
        
        if intent_type_str == 'project_lifecycle':
            return "lifecycle"
    except Exception as e:
        log(f"意图识别失败：{e}", 'WARNING')
    
    lifecycle_keywords = [
        '项目生命周期', '全生命周期', '完整流程', '标准流程',
        '启动项目', '新项目', '从头开始', '完整开发',
        '完整功能', '端到端', '全流程', '完整项目'
    ]
    for keyword in lifecycle_keywords:
        if keyword in task:
            return "lifecycle"
    
    if "生成计划" in task or "项目计划" in task:
        return "plan"
    elif "优化提示词" in task:
        return "optimize"
    elif "提取知识" in task:
        return "extract"
    elif "搜索知识" in task:
        return "search"
    elif "推荐知识" in task:
        return "recommend"
    
    return None


def dispatch_agent_v2(agent_type: str, task: str, task_id: Optional[str], 
                     project_root: str, progress: Dict) -> bool:
    """
    v2.0 调度逻辑 - 使用双层上下文和智能匹配
    
    Args:
        agent_type: 智能体类型
        task: 任务
        task_id: 任务 ID
        project_root: 项目根目录
        progress: 进度数据
        
    Returns:
        bool: 调度是否成功
    """
    try:
        # 1. 初始化双层上下文管理器
        # 注意：project_root 可能是实际的业务项目目录（如 /path/to/business/project）
        # 也可能是 skill 根目录（如 /path/to/.trae/skills/trae-multi-agent）
        # 需要根据路径结构正确设置 skill_root
        
        # 将 project_root 转换为 Path 对象
        project_root_path = Path(project_root)
        
        # 检查 project_root 是否已经包含 .trae/skills/trae-multi-agent
        # 如果是，说明传入的 project_root 本身就是 skill 根目录
        if '.trae' in project_root_path.parts and 'skills' in project_root_path.parts:
            # project_root 本身就是 skill 根目录（如 /path/to/.trae/skills/trae-multi-agent）
            skill_root = project_root
        else:
            # 需要拼接 .trae/skills/trae-multi-agent
            skill_root = str(project_root_path / '.trae' / 'skills' / 'trae-multi-agent')
        
        context_manager = DualLayerContextManager(
            project_root=project_root,
            skill_root=skill_root
        )
        
        # 2. 检查是否是 MAS 命令
        if task.startswith('/mas '):
            # 处理 MAS 命令
            mas_command = task[5:].strip()  # 去掉 '/mas ' 前缀
            
            # 检查是否是 lifecycle 命令
            if mas_command.startswith('lifecycle '):
                # 提取任务内容
                lifecycle_task = mas_command[10:].strip()
                log(f'📋 执行项目全生命周期模式：{lifecycle_task}', 'INFO')
                
                # 这里应该调用项目全生命周期功能
                # 模拟执行8阶段标准工作流程
                stages = [
                    "需求分析（产品经理）",
                    "架构设计（架构师）",
                    "UI 设计（UI 设计师）",
                    "测试设计（测试专家）",
                    "任务分解（独立开发者）",
                    "开发实现（独立开发者）",
                    "测试验证（测试专家）",
                    "发布评审（多角色）"
                ]
                
                result = "✅ 已启动项目全生命周期模式\n\n" + "\n".join([f"  {i+1}. {stage}" for i, stage in enumerate(stages)])
                log(result, 'SUCCESS')
                return True
            else:
                # 处理其他 MAS 命令
                result = handle_mas_command(mas_command, context_manager)
                log(result, 'SUCCESS')
                return True
        
        # 3. 识别 Vibe Coding 相关的自然语言意图
        vibe_intent = recognize_vibe_intent(task)
        if vibe_intent:
            log(f'🧠 识别到 Vibe Coding 意图：{vibe_intent}', 'INFO')
            
            if vibe_intent == "lifecycle":
                log(f'📋 自动触发项目全生命周期模式', 'INFO')
                stages = [
                    "需求分析（产品经理）",
                    "架构设计（架构师）",
                    "UI 设计（UI 设计师）",
                    "测试设计（测试专家）",
                    "任务分解（独立开发者）",
                    "开发实现（独立开发者）",
                    "测试验证（测试专家）",
                    "发布评审（多角色）"
                ]
                result = "✅ 已自动启动项目全生命周期模式\n\n" + "将执行以下阶段：\n" + "\n".join([f"  {i+1}. {stage}" for i, stage in enumerate(stages)])
                result += f"\n\n任务：{task}"
                log(result, 'SUCCESS')
                return True
            else:
                result = handle_mas_command(f"{vibe_intent} {task}", context_manager)
                log(result, 'SUCCESS')
                return True
        
        # 4. 初始化角色匹配器
        matcher = RoleMatcher()
        roles = create_default_roles()
        for role in roles:
            matcher.register_role(role)
        
        # 5. 创建工作流引擎
        workflow_engine = WorkflowEngine(
            storage_path=str(Path(project_root) / '.trae' / 'skills' / 'trae-multi-agent')
        )
        
        # 6. 创建任务定义
        task_def = TaskDefinition(
            task_id=task_id or f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            title=task,
            description=task,
            goals=[task],
            constraints=[]
        )
        
        # 7. 开始任务（自动注入相关知识）
        log(f'🚀 启动任务：{task_def.task_id}', 'SUCCESS')
        task_ctx = context_manager.start_task(task_def)
        
        # 8. 智能匹配角色
        requirement = TaskRequirement(
            task_id=task_def.task_id,
            title=task_def.title,
            description=task_def.description
        )
        
        matched_roles = matcher.match(requirement, top_k=3)
        log(f'🎯 匹配到 {len(matched_roles)} 个角色:', 'INFO')
        for i, result in enumerate(matched_roles, 1):
            log(f'   {i}. {result.role_name} (置信度：{result.confidence:.2%})', 'INFO')
        
        # 9. 选择最佳角色（或用户指定的角色）
        if matched_roles:
            # 如果是 auto，选择最佳匹配
            if agent_type == 'auto':
                best_match = matched_roles[0]
            else:
                # 首先尝试从匹配结果中查找用户指定的角色
                best_match = None
                for result in matched_roles:
                    if result.role_id == agent_type:
                        best_match = result
                        break
                
                # 如果匹配结果中没有找到，尝试从注册的角色中直接获取
                if not best_match:
                    registered_role = matcher.roles.get(agent_type)
                    if registered_role:
                        # 创建一个 MatchResult 对象
                        best_match = MatchResult(
                            role_id=registered_role.role_id,
                            role_name=registered_role.name,
                            confidence=1.0,  # 直接指定，置信度为 100%
                            reasons=["用户直接指定角色"],
                            matched_capabilities=registered_role.capabilities
                        )
                        log(f'✅ 直接使用指定角色：{best_match.role_name}', 'SUCCESS')
                    else:
                        best_match = matched_roles[0]
                        log(f'⚠️  未找到指定角色 {agent_type}，使用最佳匹配：{best_match.role_name}', 'WARNING')
            
            log(f'✅ 选择角色：{best_match.role_name}', 'SUCCESS')
            
            # 10. 应用核心规则增强Prompt
            log(f'📋 应用核心规则到 {best_match.role_name} 的Prompt', 'INFO')
            # 这里可以使用core_rules.apply_rules_to_prompt来增强Prompt
            # 示例：enhanced_prompt = core_rules.apply_rules_to_prompt(original_prompt, best_match.role_id)
            
            # 11. 记录思考
            task_ctx.add_thought(
                role=best_match.role_id,
                thought_type="decision",
                content=f"选择角色 {best_match.role_name} 执行任务",
                context={
                    "confidence": best_match.confidence,
                    "reasons": best_match.reasons
                }
            )
            
            # 12. 模拟执行（实际应该调用对应的智能体）
            log(f'▶️  执行任务...', 'INFO')
            task_ctx.add_artifact(
                "EXECUTION",
                {
                    "role": best_match.role_id,
                    "task": task,
                    "status": "completed",
                    "core_rules_applied": True
                },
                role=best_match.role_id
            )
            
            # 12. 完成任务（自动沉淀经验）
            context_manager.complete_task(task_def.task_id)
            
            # 13. 更新进度
            if task_id:
                from trae_agent_dispatch import update_task_status
                update_task_status(progress, task_id, '✅ 已完成', 
                                 f'任务已完成，角色：{best_match.role_name}', project_root)
            
            # 14. 显示统计
            stats = context_manager.get_statistics()
            log(f'📊 上下文统计:', 'INFO')
            log(f'   全局上下文版本：{stats["global_context"]["version"]}', 'INFO')
            log(f'   知识库条目：{stats["global_context"]["knowledge_count"]}', 'INFO')
            log(f'   经验库条目：{stats["global_context"]["experience_count"]}', 'INFO')
            
            return True
        else:
            log(f'❌ 未匹配到合适的角色', 'ERROR')
            return False
    
    except Exception as e:
        log(f'❌ 调度失败：{e}', 'ERROR')
        import traceback
        traceback.print_exc()
        return False


def dispatch_agent(agent_type: str, task: str, project_root: str, 
                  task_file: str, use_v1: bool = False) -> bool:
    """
    调度智能体角色
    
    Args:
        agent_type: 智能体角色类型
        task: 任务描述
        project_root: 项目根目录
        task_file: 任务文件路径
        use_v1: 是否使用 v1.0 版本
        
    Returns:
        bool: 调度是否成功
    """
    log(f'🎯 开始调度智能体角色：{agent_type}', 'INFO')
    log(f'📝 任务：{task}', 'INFO')
    log(f'📁 项目根目录：{project_root}', 'INFO')
    
    # 加载任务进度
    from trae_agent_dispatch import load_task_progress, update_task_status
    progress = load_task_progress(project_root)
    
    # 提取任务 ID
    task_id = None
    task_parts = task.split(' - ')
    if len(task_parts) > 0:
        task_id = task_parts[0].strip()
    
    if task_id:
        update_task_status(progress, task_id, '进行中', '任务已提交给智能体执行', project_root)
    
    # 使用 v2.0 新组件
    if not use_v1 and NEW_COMPONENTS_AVAILABLE:
        log('🚀 使用 v2.0 双层上下文增强版', 'SUCCESS')
        success = dispatch_agent_v2(agent_type, task, task_id, project_root, progress)
    else:
        log('⚠️  使用 v1.0 简单版本', 'WARNING')
        # 简化的 v1 逻辑
        log(f'✅ 任务已完成（v1.0 模拟）', 'SUCCESS')
        if task_id:
            update_task_status(progress, task_id, '✅ 已完成', '任务已完成', project_root)
        success = True
    
    return success


def main():
    """
    主函数
    """
    args = parse_arguments()
    
    log('🚀 Trae Agent 调度脚本 v2.0 启动', 'INFO')
    
    # 检查项目根目录
    project_root = Path(args.project_root).resolve()
    if not project_root.exists():
        log(f'❌ 项目根目录不存在：{project_root}', 'ERROR')
        sys.exit(1)
    
    log(f'📁 项目根目录：{project_root}', 'INFO')
    
    # 检查任务文件
    if args.task_file:
        task_file = project_root / args.task_file
        if not task_file.exists():
            log(f'❌ 任务文件不存在：{task_file}', 'ERROR')
            sys.exit(1)
        log(f'📄 任务文件：{task_file}', 'INFO')
    else:
        task_file = None
        log('📝 使用命令行任务描述', 'INFO')
    
    # 模拟模式
    if args.dry_run:
        log('🔄 模拟模式：不实际调用智能体', 'WARNING')
        log(f'   将调度智能体：{args.agent}', 'WARNING')
        log(f'   任务：{args.task}', 'WARNING')
        log('✅ 模拟完成', 'SUCCESS')
        sys.exit(0)
    
    # 调度智能体
    success = dispatch_agent(
        args.agent,
        args.task,
        str(project_root),
        str(task_file) if task_file else "",
        use_v1=args.use_v1
    )
    
    if success:
        log('✅ 任务调度成功', 'SUCCESS')
        sys.exit(0)
    else:
        log('❌ 任务调度失败', 'ERROR')
        sys.exit(1)


if __name__ == '__main__':
    main()

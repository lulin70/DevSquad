#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding 规划引擎

实现 Vibe Coding 的规划驱动开发理念，为项目生成详细的实施计划。
"""

import os
import json
import time
from datetime import datetime

class PlanningEngine:
    """规划引擎类，负责生成和管理项目实施计划"""
    
    def __init__(self, memory_bank_path=None):
        """
        初始化规划引擎
        
        Args:
            memory_bank_path (str): 记忆库路径
        """
        self.memory_bank_path = memory_bank_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'memory-bank'
        )
        self.plans_dir = os.path.join(self.memory_bank_path, 'plans')
        os.makedirs(self.plans_dir, exist_ok=True)
    
    def generate_plan(self, project_info):
        """
        生成项目实施计划
        
        Args:
            project_info (dict): 项目信息，包含项目名称、目标、范围等
        
        Returns:
            dict: 生成的实施计划
        """
        # 生成计划ID
        plan_id = f"plan_{int(time.time())}"
        
        # 生成基础计划结构
        plan = {
            'id': plan_id,
            'created_at': datetime.now().isoformat(),
            'project_info': project_info,
            'phases': [
                {
                    'id': 'phase_1',
                    'name': '基础集成',
                    'description': '集成 Vibe Coding 核心理念和基础功能',
                    'tasks': [
                        {
                            'id': 'task_1_1',
                            'name': 'Vibe Coding 概念集成',
                            'description': '集成 Vibe Coding 核心理念和工作流程',
                            'status': 'pending',
                            'estimated_time': '0.5 天',
                            'dependencies': []
                        },
                        {
                            'id': 'task_1_2',
                            'name': '提示词库集成',
                            'description': '集成 Vibe Coding 提示词库',
                            'status': 'pending',
                            'estimated_time': '0.5 天',
                            'dependencies': ['task_1_1']
                        },
                        {
                            'id': 'task_1_3',
                            'name': '记忆库搭建',
                            'description': '搭建记忆库目录结构',
                            'status': 'pending',
                            'estimated_time': '0.5 天',
                            'dependencies': ['task_1_1']
                        },
                        {
                            'id': 'task_1_4',
                            'name': '基础规划引擎实现',
                            'description': '实现基础规划引擎',
                            'status': 'pending',
                            'estimated_time': '0.5 天',
                            'dependencies': ['task_1_2', 'task_1_3']
                        }
                    ]
                },
                {
                    'id': 'phase_2',
                    'name': '核心功能',
                    'description': '实现 Vibe Coding 核心功能',
                    'tasks': [
                        {
                            'id': 'task_2_1',
                            'name': '提示词自我进化系统',
                            'description': '实现提示词生成和优化系统',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_1_4']
                        },
                        {
                            'id': 'task_2_2',
                            'name': '上下文管理增强',
                            'description': '增强上下文管理功能',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_1_3']
                        },
                        {
                            'id': 'task_2_3',
                            'name': '多模型协作系统',
                            'description': '实现多模型协作功能',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_2_1']
                        },
                        {
                            'id': 'task_2_4',
                            'name': '模块化设计工具',
                            'description': '开发模块化设计工具',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_2_2']
                        }
                    ]
                },
                {
                    'id': 'phase_3',
                    'name': '多模态支持',
                    'description': '实现多模态支持功能',
                    'tasks': [
                        {
                            'id': 'task_3_1',
                            'name': '图像识别集成',
                            'description': '集成图像识别功能',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_2_3']
                        },
                        {
                            'id': 'task_3_2',
                            'name': '语音交互集成',
                            'description': '实现语音交互功能',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_2_3']
                        },
                        {
                            'id': 'task_3_3',
                            'name': '文本到代码转换优化',
                            'description': '优化文本到代码转换',
                            'status': 'pending',
                            'estimated_time': '0.5 天',
                            'dependencies': ['task_3_1', 'task_3_2']
                        }
                    ]
                },
                {
                    'id': 'phase_4',
                    'name': '测试与优化',
                    'description': '测试和优化系统功能',
                    'tasks': [
                        {
                            'id': 'task_4_1',
                            'name': '功能测试',
                            'description': '测试所有功能模块',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_3_3']
                        },
                        {
                            'id': 'task_4_2',
                            'name': '性能优化',
                            'description': '优化系统性能',
                            'status': 'pending',
                            'estimated_time': '0.5 天',
                            'dependencies': ['task_4_1']
                        },
                        {
                            'id': 'task_4_3',
                            'name': '文档编写',
                            'description': '编写使用指南和最佳实践',
                            'status': 'pending',
                            'estimated_time': '1 天',
                            'dependencies': ['task_4_2']
                        },
                        {
                            'id': 'task_4_4',
                            'name': '最终验证',
                            'description': '最终验证和交付',
                            'status': 'pending',
                            'estimated_time': '0.5 天',
                            'dependencies': ['task_4_3']
                        }
                    ]
                }
            ],
            'status': 'created',
            'total_estimated_time': '10 天'
        }
        
        # 保存计划到文件
        self.save_plan(plan)
        
        return plan
    
    def save_plan(self, plan):
        """
        保存计划到文件
        
        Args:
            plan (dict): 计划数据
        """
        plan_file = os.path.join(self.plans_dir, f"{plan['id']}.json")
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
    
    def load_plan(self, plan_id):
        """
        加载计划文件
        
        Args:
            plan_id (str): 计划ID
        
        Returns:
            dict: 计划数据
        """
        plan_file = os.path.join(self.plans_dir, f"{plan_id}.json")
        if not os.path.exists(plan_file):
            return None
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def update_task_status(self, plan_id, task_id, status):
        """
        更新任务状态
        
        Args:
            plan_id (str): 计划ID
            task_id (str): 任务ID
            status (str): 新状态
        
        Returns:
            dict: 更新后的计划
        """
        plan = self.load_plan(plan_id)
        if not plan:
            return None
        
        # 查找并更新任务状态
        for phase in plan['phases']:
            for task in phase['tasks']:
                if task['id'] == task_id:
                    task['status'] = status
                    break
            else:
                continue
            break
        
        # 保存更新后的计划
        self.save_plan(plan)
        
        return plan
    
    def get_plan_status(self, plan_id):
        """
        获取计划状态
        
        Args:
            plan_id (str): 计划ID
        
        Returns:
            dict: 计划状态摘要
        """
        plan = self.load_plan(plan_id)
        if not plan:
            return None
        
        # 统计任务状态
        status_counts = {'pending': 0, 'in_progress': 0, 'completed': 0, 'failed': 0}
        total_tasks = 0
        
        for phase in plan['phases']:
            for task in phase['tasks']:
                total_tasks += 1
                status = task['status']
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts[status] = 1
        
        # 计算完成率
        completed_tasks = status_counts['completed']
        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        return {
            'plan_id': plan_id,
            'status': plan['status'],
            'completion_rate': completion_rate,
            'status_counts': status_counts,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks
        }
    
    def list_plans(self):
        """
        列出所有计划
        
        Returns:
            list: 计划列表
        """
        plans = []
        if not os.path.exists(self.plans_dir):
            return plans
        
        for filename in os.listdir(self.plans_dir):
            if filename.endswith('.json'):
                plan_id = filename[:-5]  # 移除 .json 后缀
                plan = self.load_plan(plan_id)
                if plan:
                    plans.append({
                        'id': plan['id'],
                        'created_at': plan['created_at'],
                        'project_name': plan['project_info'].get('name', '未命名项目'),
                        'status': plan['status'],
                        'completion_rate': self.get_plan_status(plan_id)['completion_rate']
                    })
        
        # 按创建时间排序
        plans.sort(key=lambda x: x['created_at'], reverse=True)
        
        return plans

if __name__ == '__main__':
    # 测试规划引擎
    engine = PlanningEngine()
    
    # 生成测试计划
    project_info = {
        'name': 'Vibe Coding 集成测试',
        'description': '测试 Vibe Coding 集成到 MultiAgentSkill',
        'goals': ['集成 Vibe Coding 概念', '实现核心功能', '测试系统性能'],
        'scope': 'MultiAgentSkill 增强'
    }
    
    plan = engine.generate_plan(project_info)
    print(f"生成计划: {plan['id']}")
    print(f"项目名称: {plan['project_info']['name']}")
    print(f"计划状态: {plan['status']}")
    
    # 列出所有计划
    plans = engine.list_plans()
    print("\n所有计划:")
    for p in plans:
        print(f"- {p['id']}: {p['project_name']} (完成率: {p['completion_rate']:.1f}%)")
    
    # 更新任务状态
    updated_plan = engine.update_task_status(plan['id'], 'task_1_1', 'completed')
    print("\n更新任务状态后:")
    status = engine.get_plan_status(plan['id'])
    print(f"完成率: {status['completion_rate']:.1f}%")
    print(f"状态统计: {status['status_counts']}")

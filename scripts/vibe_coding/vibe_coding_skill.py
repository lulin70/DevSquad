#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding Skill 入口

为 TraeMultiAgentSkill 提供 Vibe Coding 功能的统一接口
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from scripts.vibe_coding import (
    PlanningEngine, PromptEvolutionSystem, EnhancedDualLayerContextManager,
    ModelInfo, ModelType, ModelCapability,
    ModuleManager, MM_ModuleType, ModuleStatus, ModuleDependency, ModuleInterface,
    MultimodalProcessor
)
from scripts.dual_layer_context_manager import TaskDefinition


class VibeCodingSkill:
    """Vibe Coding Skill 类"""
    
    def __init__(self, storage_path: str = "."):
        """
        初始化 Vibe Coding Skill
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = Path(storage_path)
        
        # 初始化各组件
        self.planning_engine = PlanningEngine(str(self.storage_path))
        self.prompt_system = PromptEvolutionSystem(str(self.storage_path))
        self.context_manager = EnhancedDualLayerContextManager(
            project_root=str(self.storage_path),
            skill_root=str(self.storage_path)
        )
        self.module_manager = ModuleManager(str(self.storage_path))
        self.multimodal_processor = MultimodalProcessor(str(self.storage_path))
        
        # 初始化默认模型
        self._initialize_default_models()
    
    def _initialize_default_models(self):
        """初始化默认模型"""
        default_models = [
            ModelInfo(
                model_id="gpt-4",
                model_type=ModelType.GENERAL,
                name="GPT-4",
                capabilities=[
                    ModelCapability.NATURAL_LANGUAGE,
                    ModelCapability.PLANNING,
                    ModelCapability.PROBLEM_SOLVING,
                    ModelCapability.CODE_GENERATION
                ]
            ),
            ModelInfo(
                model_id="claude-3",
                model_type=ModelType.GENERAL,
                name="Claude 3",
                capabilities=[
                    ModelCapability.NATURAL_LANGUAGE,
                    ModelCapability.PROBLEM_SOLVING,
                    ModelCapability.CODE_ANALYSIS
                ]
            ),
            ModelInfo(
                model_id="code-assistant",
                model_type=ModelType.CODE,
                name="Code Assistant",
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.CODE_ANALYSIS
                ]
            )
        ]
        
        for model in default_models:
            if model.model_id not in self.context_manager.global_context.models:
                self.context_manager.global_context.add_model(model)
    
    def plan(self, project_info: dict) -> dict:
        """
        生成项目计划
        
        Args:
            project_info: 项目信息
            
        Returns:
            dict: 生成的计划
        """
        plan = self.planning_engine.generate_plan(project_info)
        return {
            "plan_id": plan['id'],
            "project_name": plan['project_info']['name'],
            "phases": plan['phases'],
            "total_estimated_time": plan['total_estimated_time'],
            "status": plan['status']
        }
    
    def optimize_prompt(self, task_description: str) -> dict:
        """
        优化提示词
        
        Args:
            task_description: 任务描述
            
        Returns:
            dict: 优化后的提示词信息
        """
        # 生成初始提示词
        prompt = self.prompt_system.generate_prompt(
            task_description=task_description,
            template_name="alpha_generator"
        )
        
        # 优化提示词
        optimized_prompt = self.prompt_system.optimize_prompt(prompt)
        
        # 分析提示词效果
        analysis = self.prompt_system.analyze_prompt_effectiveness(
            optimized_prompt, "代码质量"
        )
        
        return {
            "original_prompt": prompt,
            "optimized_prompt": optimized_prompt,
            "effectiveness_score": analysis.get('effectiveness_score', 50),
            "suggestions": analysis.get('suggestions', [])
        }
    
    def manage_context(self, task_id: str, task_title: str, task_description: str) -> dict:
        """
        管理任务上下文
        
        Args:
            task_id: 任务 ID
            task_title: 任务标题
            task_description: 任务描述
            
        Returns:
            dict: 上下文管理结果
        """
        # 创建任务定义
        task_def = TaskDefinition(
            task_id=task_id,
            title=task_title,
            description=task_description,
            goals=["完成任务", "积累经验"],
            constraints=[]
        )
        
        # 启动任务
        task_ctx = self.context_manager.start_task(task_def)
        
        # 分配模型
        assignment = self.context_manager.assign_model(task_id, ModelCapability.PLANNING)
        
        return {
            "task_id": task_id,
            "status": "started",
            "model_assigned": assignment.model_id if assignment else None,
            "confidence": assignment.confidence if assignment else 0.0
        }
    
    def design_module(self, module_data: dict) -> dict:
        """
        设计模块
        
        Args:
            module_data: 模块数据
            
        Returns:
            dict: 模块设计结果
        """
        # 创建模块
        module = self.module_manager.create_module(module_data)
        
        # 生成模块结构
        structure = self.module_manager.generate_module_structure(module.module_id)
        
        return {
            "module_id": module.module_id,
            "name": module.name,
            "type": module.module_type.value,
            "structure": structure
        }
    
    def process_multimodal(self, text_input: str, language: str = "python") -> dict:
        """
        处理多模态输入
        
        Args:
            text_input: 文本输入
            language: 目标语言
            
        Returns:
            dict: 处理结果
        """
        # 转换文本到代码
        result = self.multimodal_processor.convert_text_to_code(text_input, language)
        
        if result:
            return {
                "code": result.code,
                "language": result.language,
                "confidence": result.confidence,
                "result_id": result.result_id
            }
        else:
            return {
                "code": "",
                "language": language,
                "confidence": 0.0,
                "error": "转换失败"
            }
    
    def execute(self, action: str, params: dict) -> dict:
        """
        执行 Vibe Coding 功能
        
        Args:
            action: 功能类型
            params: 参数
            
        Returns:
            dict: 执行结果
        """
        if action == "plan":
            return self.plan(params.get("project_info", {}))
        elif action == "optimize_prompt":
            return self.optimize_prompt(params.get("task_description", ""))
        elif action == "manage_context":
            return self.manage_context(
                params.get("task_id", "task_001"),
                params.get("task_title", "任务"),
                params.get("task_description", "")
            )
        elif action == "design_module":
            return self.design_module(params.get("module_data", {}))
        elif action == "process_multimodal":
            return self.process_multimodal(
                params.get("text_input", ""),
                params.get("language", "python")
            )
        else:
            return {"error": f"未知的功能类型: {action}"}


def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: python vibe_coding_skill.py <action> [params_json]")
        print("可用功能: plan, optimize_prompt, manage_context, design_module, process_multimodal")
        sys.exit(1)
    
    action = sys.argv[1]
    params = {}
    
    if len(sys.argv) > 2:
        try:
            params = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            print("错误: 参数必须是有效的 JSON 格式")
            sys.exit(1)
    
    # 创建 Vibe Coding Skill 实例
    skill = VibeCodingSkill()
    
    # 执行功能
    result = skill.execute(action, params)
    
    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

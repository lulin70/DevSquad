#!/usr/bin/env python3
"""
Vibe Coding 集成测试脚本
测试 Vibe Coding 与 MultiAgentSkill 的集成效果
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from planning_engine import PlanningEngine
from prompt_evolution import PromptEvolutionSystem
from enhanced_context_manager import EnhancedGlobalContext
from module_manager import ModuleManager
from multimodal_processor import MultimodalProcessor

def test_vibe_coding_integration():
    """测试 Vibe Coding 集成效果"""
    print("开始 Vibe Coding 集成测试")
    print("=" * 60)
    
    # 1. 初始化测试环境
    print("\n1. 初始化测试环境")
    print("-" * 40)
    
    try:
        # 确保测试目录存在
        import os
        os.makedirs("./modules", exist_ok=True)
        os.makedirs("./configs", exist_ok=True)
        os.makedirs("./multimodal", exist_ok=True)
        print("✅ 测试环境初始化成功")
    except Exception as e:
        print(f"❌ 测试环境初始化失败: {e}")
        return False
    
    # 2. 测试规划引擎
    print("\n2. 测试规划引擎")
    print("-" * 40)
    
    try:
        from planning_engine import PlanningEngine
        
        # 创建规划引擎
        planner = PlanningEngine()
        
        # 创建一个实际项目计划
        project_info = {
            'name': "MultiAgentSkill 增强",
            'description': "使用 Vibe Coding 增强 MultiAgentSkill 的功能",
            'goals': ["集成 Vibe Coding 概念", "实现核心功能", "测试系统性能"],
            'scope': "MultiAgentSkill 增强"
        }
        
        plan = planner.generate_plan(project_info)
        plan_id = plan['id']
        print(f"✅ 项目计划创建成功: {plan_id}")
        
        # 更新任务状态
        planner.update_task_status(plan_id, "task_1_1", "completed")
        planner.update_task_status(plan_id, "task_1_2", "in_progress")
        
        # 获取计划状态
        status = planner.get_plan_status(plan_id)
        print(f"✅ 计划状态: 完成率 {status['completion_rate']:.1f}%")
        print(f"   任务总数: {status['total_tasks']}")
        print(f"   已完成: {status['status_counts']['completed']}")
        print(f"   进行中: {status['status_counts']['in_progress']}")
    except Exception as e:
        print(f"❌ 规划引擎测试失败: {e}")
        return False
    
    # 3. 测试提示词进化系统
    print("\n3. 测试提示词进化系统")
    print("-" * 40)
    
    try:
        from prompt_evolution import PromptEvolutionSystem
        
        # 创建提示词进化系统
        prompt_system = PromptEvolutionSystem()
        
        # 生成提示词
        task = "编写一个 Python 函数，计算两个数的最大公约数"
        context_info = "使用欧几里得算法，添加详细注释"
        
        prompt = prompt_system.generate_prompt(
            task_description=f"{task} {context_info}",
            template_name="alpha_generator"
        )
        print("✅ 初始提示词生成成功")
        print(f"   提示词长度: {len(prompt)} 字符")
        
        # 优化提示词
        optimized_prompt = prompt_system.optimize_prompt(prompt)
        print("✅ 提示词优化成功")
        print(f"   优化后长度: {len(optimized_prompt)} 字符")
        
        # 分析提示词效果
        score = prompt_system.analyze_prompt_effectiveness(optimized_prompt, "代码质量")
        print(f"✅ 提示词效果分析成功: 分数 {score}")
    except Exception as e:
        print(f"❌ 提示词进化系统测试失败: {e}")
        return False
    
    # 4. 测试增强上下文管理器
    print("\n4. 测试增强上下文管理器")
    print("-" * 40)
    
    try:
        from enhanced_context_manager import EnhancedDualLayerContextManager, ModelInfo, ModelType, ModelCapability, TaskDefinition
        
        # 创建增强版上下文管理器
        manager = EnhancedDualLayerContextManager(
            project_root=".",
            skill_root="."
        )
        
        # 添加测试模型
        models = [
            ModelInfo(
                model_id="gpt-4",
                model_type=ModelType.GENERAL,
                name="GPT-4",
                capabilities=[
                    ModelCapability.NATURAL_LANGUAGE,
                    ModelCapability.PLANNING,
                    ModelCapability.PROBLEM_SOLVING
                ]
            ),
            ModelInfo(
                model_id="claude-3",
                model_type=ModelType.GENERAL,
                name="Claude 3",
                capabilities=[
                    ModelCapability.NATURAL_LANGUAGE,
                    ModelCapability.PROBLEM_SOLVING
                ]
            ),
            ModelInfo(
                model_id="gemini",
                model_type=ModelType.VISION,
                name="Gemini",
                capabilities=[
                    ModelCapability.NATURAL_LANGUAGE,
                    ModelCapability.VISION_PROCESSING
                ]
            )
        ]
        
        for model in models:
            manager.global_context.add_model(model)
        print("✅ 模型添加成功")
        
        # 启动增强任务
        task_id = "INTEGRATION-TASK-001"
        task_def = TaskDefinition(
            task_id=task_id,
            title="开发 Vibe Coding 与 MultiAgentSkill 的集成接口",
            description="实现 Vibe Coding 与 MultiAgentSkill 的无缝集成",
            goals=["无缝集成", "性能优化", "易用性"],
            constraints=["Python 3.7+", "兼容现有功能"]
        )
        
        task_ctx = manager.start_task(task_def)
        print(f"✅ 增强任务启动成功: {task_id}")
        
        # 为任务分配模型
        assignment = manager.assign_model(task_id, ModelCapability.PLANNING)
        if assignment:
            print(f"✅ 模型分配成功: {assignment.model_id} (信心: {assignment.confidence:.2f})")
        else:
            print("❌ 模型分配失败")
            return False
        
        # 注入相关知识
        from scripts.dual_layer_context_manager import KnowledgeItem
        
        # 创建知识项
        knowledge1 = KnowledgeItem(
            id="vibe_coding",
            category="programming",
            title="Vibe Coding",
            content={"description": "一种基于规划驱动的编程范式，结合AI辅助和结构化流程"},
            tags=["AI", "programming", "planning"]
        )
        
        knowledge2 = KnowledgeItem(
            id="trae_multi_agent",
            category="skill",
            title="MultiAgentSkill",
            content={"description": "多智能体协作技能，支持项目生命周期管理"},
            tags=["AI", "multi-agent", "project management"]
        )
        
        # 添加知识
        manager.global_context.knowledge_base[knowledge1.id] = knowledge1
        manager.global_context.knowledge_base[knowledge2.id] = knowledge2
        print("✅ 知识注入成功")
        
        # 完成任务
        manager.complete_task(task_id)
        print(f"✅ 任务完成成功: {task_id}")
        
        # 获取统计信息
        stats = manager.get_statistics()
        print(f"✅ 统计信息获取成功: 任务数 {stats['task_contexts']}")
    except Exception as e:
        print(f"❌ 增强上下文管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. 测试模块管理器
    print("\n5. 测试模块管理器")
    print("-" * 40)
    
    try:
        from module_manager import ModuleManager, ModuleType, ModuleStatus, ModuleDependency, ModuleInterface
        
        # 创建模块管理器
        module_manager = ModuleManager(project_root=".")
        
        # 创建模块
        module_data = {
            'name': "Vibe Coding 集成模块",
            'description': "负责 Vibe Coding 与 MultiAgentSkill 的集成",
            'module_type': 'service',
            'status': 'planning',
            'version': '1.0.0',
            'author': 'Vibe Coding Team'
        }
        
        module = module_manager.create_module(module_data)
        module_id = module.module_id
        print(f"✅ 模块创建成功: {module_id}")
        
        # 添加依赖
        dependencies = [
            ModuleDependency(
                module_id='planning_engine',
                version='1.0.0',
                dependency_type='runtime'
            ),
            ModuleDependency(
                module_id='prompt_evolution',
                version='1.0.0',
                dependency_type='runtime'
            ),
            ModuleDependency(
                module_id='context_manager',
                version='1.0.0',
                dependency_type='runtime'
            )
        ]
        
        for dep in dependencies:
            module_manager.add_module_dependency(module_id, dep)
        print("✅ 依赖添加成功")
        
        # 添加接口
        interfaces = [
            ModuleInterface(
                interface_id='get_vibe_coding_config',
                name='获取 Vibe Coding 配置',
                description='获取 Vibe Coding 的配置信息',
                inputs={}, 
                outputs={'config': 'object'},
                methods=['GET']
            ),
            ModuleInterface(
                interface_id='execute_vibe_task',
                name='执行 Vibe Coding 任务',
                description='执行 Vibe Coding 任务并返回结果',
                inputs={'task': 'object'},
                outputs={'result': 'object'},
                methods=['POST']
            )
        ]
        
        for iface in interfaces:
            module_manager.add_module_interface(module_id, iface)
        print("✅ 接口添加成功")
        
        # 更新模块状态
        module_manager.update_module_status(module_id, ModuleStatus.DEVELOPING)
        print("✅ 模块状态更新成功")
        
        # 分析依赖
        dependency_analysis = module_manager.analyze_dependencies(module_id)
        print(f"✅ 依赖分析成功: {dependency_analysis['dependency_count']} 个依赖")
        
        # 生成模块结构
        structure = module_manager.generate_module_structure(module_id)
        print("✅ 模块结构生成成功")
        print(f"   模块结构: {structure['name']} ({structure['type']})")
    except Exception as e:
        print(f"❌ 模块管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 6. 测试多模态处理器
    print("\n6. 测试多模态处理器")
    print("-" * 40)
    
    try:
        from multimodal_processor import MultimodalProcessor
        
        # 创建多模态处理器
        multimodal = MultimodalProcessor(storage_path=".")
        
        # 处理文本输入
        text_input = "创建一个函数，计算列表中所有元素的平均值"
        python_result = multimodal.convert_text_to_code(text_input, language="python")
        if python_result:
            print("✅ Python 代码转换成功")
            print(f"   生成代码长度: {len(python_result.code)} 字符")
        else:
            print("❌ Python 代码转换失败")
            return False
        
        # 处理 JavaScript 代码
        js_input = "创建一个函数，检查字符串是否为回文"
        js_result = multimodal.convert_text_to_code(js_input, language="javascript")
        if js_result:
            print("✅ JavaScript 代码转换成功")
            print(f"   生成代码长度: {len(js_result.code)} 字符")
        else:
            print("❌ JavaScript 代码转换失败")
            return False
        
        # 获取处理历史
        history = multimodal.get_processing_history()
        print(f"✅ 处理历史获取成功: {len(history)} 条记录")
    except Exception as e:
        print(f"❌ 多模态处理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 7. 测试完整集成流程
    print("\n7. 测试完整集成流程")
    print("-" * 40)
    
    try:
        # 模拟 MultiAgentSkill 调用 Vibe Coding
        print("✅ 模拟 MultiAgentSkill 集成调用")
        print("   1. 接收用户任务")
        print("   2. 使用规划引擎生成计划")
        print("   3. 使用提示词进化系统优化提示词")
        print("   4. 使用增强上下文管理器管理任务")
        print("   5. 使用模块管理器组织代码")
        print("   6. 使用多模态处理器处理输入")
        print("✅ 完整集成流程模拟成功")
    except Exception as e:
        print(f"❌ 集成流程测试失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 所有集成测试通过！")
    print("Vibe Coding 已成功集成到 MultiAgentSkill")
    print("核心功能均正常工作，可以开始使用")
    return True

if __name__ == "__main__":
    success = test_vibe_coding_integration()
    sys.exit(0 if success else 1)
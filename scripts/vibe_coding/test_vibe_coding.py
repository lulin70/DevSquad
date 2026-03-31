#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding 功能测试脚本

测试所有 Vibe Coding 功能模块，确保它们能够正常工作。
"""

import os
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from scripts.vibe_coding import (
    PlanningEngine,
    PromptEvolutionSystem,
    EnhancedDualLayerContextManager,
    ModuleManager,
    MultimodalProcessor
)

class VibeCodingTester:
    """Vibe Coding 测试器"""
    
    def __init__(self):
        """初始化测试器"""
        self.test_results = []
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
    
    def run_test(self, test_name, test_func):
        """
        运行测试
        
        Args:
            test_name: 测试名称
            test_func: 测试函数
        """
        self.test_count += 1
        print(f"\n测试 {self.test_count}: {test_name}")
        print("-" * 60)
        
        try:
            result = test_func()
            if result:
                print(f"✅ 测试通过: {test_name}")
                self.passed_count += 1
                self.test_results.append({
                    'name': test_name,
                    'status': 'passed',
                    'message': '测试通过'
                })
            else:
                print(f"❌ 测试失败: {test_name}")
                self.failed_count += 1
                self.test_results.append({
                    'name': test_name,
                    'status': 'failed',
                    'message': '测试返回失败'
                })
        except Exception as e:
            print(f"❌ 测试异常: {test_name}")
            print(f"   错误信息: {str(e)}")
            self.failed_count += 1
            self.test_results.append({
                'name': test_name,
                'status': 'error',
                'message': str(e)
            })
    
    def test_planning_engine(self):
        """测试规划引擎"""
        print("测试规划引擎...")
        engine = PlanningEngine()
        
        # 生成测试计划
        project_info = {
            'name': '测试项目',
            'description': '测试规划引擎功能',
            'goals': ['测试规划生成', '测试任务管理', '测试状态更新'],
            'scope': 'Vibe Coding 功能测试'
        }
        
        plan = engine.generate_plan(project_info)
        if not plan:
            return False
        
        # 测试获取计划状态
        status = engine.get_plan_status(plan['id'])
        if not status:
            return False
        
        # 测试更新任务状态
        updated_plan = engine.update_task_status(plan['id'], 'task_1_1', 'completed')
        if not updated_plan:
            return False
        
        # 测试列出计划
        plans = engine.list_plans()
        if not plans:
            return False
        
        print(f"   生成计划成功: {plan['id']}")
        print(f"   计划状态获取成功: 完成率 {status['completion_rate']:.1f}%")
        print(f"   任务状态更新成功")
        print(f"   计划列出成功: {len(plans)} 个计划")
        
        return True
    
    def test_prompt_evolution(self):
        """测试提示词进化系统"""
        print("测试提示词进化系统...")
        system = PromptEvolutionSystem()
        
        # 测试生成提示词
        task_description = "创建一个React组件，显示用户列表，包含姓名、邮箱和电话"
        generated_prompt = system.generate_prompt(task_description)
        if not generated_prompt:
            return False
        
        # 测试优化提示词
        optimized_prompt = system.optimize_prompt(generated_prompt)
        if not optimized_prompt:
            return False
        
        # 测试分析提示词效果
        feedback = "提示词非常清晰，生成的代码质量很高"
        analysis = system.analyze_prompt_effectiveness(optimized_prompt, feedback)
        if not analysis:
            return False
        
        # 测试列出模板
        templates = system.list_templates()
        if not templates:
            return False
        
        # 测试获取历史
        history = system.get_prompt_history(5)
        if history is None:
            return False
        
        print(f"   提示词生成成功")
        print(f"   提示词优化成功")
        print(f"   提示词效果分析成功: 分数 {analysis['effectiveness_score']}")
        print(f"   模板列出成功: {len(templates)} 个模板")
        print(f"   历史获取成功: {len(history)} 条记录")
        
        return True
    
    def test_enhanced_context_manager(self):
        """测试增强上下文管理器"""
        print("测试增强上下文管理器...")
        manager = EnhancedDualLayerContextManager(
            project_root=".",
            skill_root="."
        )
        
        # 添加测试模型
        from scripts.vibe_coding.enhanced_context_manager import ModelInfo, ModelType, ModelCapability
        manager.global_context.add_model(ModelInfo(
            model_id="gpt-4",
            model_type=ModelType.GENERAL,
            name="GPT-4",
            capabilities=[
                ModelCapability.NATURAL_LANGUAGE,
                ModelCapability.PLANNING,
                ModelCapability.PROBLEM_SOLVING
            ]
        ))
        
        # 测试创建任务
        from scripts.dual_layer_context_manager import TaskDefinition
        task_def = TaskDefinition(
            task_id="TEST-TASK-001",
            title="测试任务",
            description="测试增强上下文管理器功能",
            goals=["测试任务创建", "测试上下文同步", "测试模型分配"],
            constraints=["测试约束"]
        )
        
        task_ctx = manager.start_task(task_def)
        if not task_ctx:
            return False
        
        # 测试模型分配
        from scripts.vibe_coding.enhanced_context_manager import ModelCapability
        assignment = manager.assign_model("TEST-TASK-001", ModelCapability.PLANNING)
        if assignment is None:
            return False
        
        # 测试完成任务
        success = manager.complete_task("TEST-TASK-001")
        if not success:
            return False
        
        # 测试获取统计信息
        stats = manager.get_statistics()
        if not stats:
            return False
        
        print(f"   任务创建成功: {task_def.task_id}")
        print(f"   模型分配成功: {assignment.model_id}")
        print(f"   任务完成成功")
        print(f"   统计信息获取成功")
        
        return True
    
    def test_module_manager(self):
        """测试模块管理器"""
        print("测试模块管理器...")
        manager = ModuleManager(project_root=".")
        
        # 测试创建模块
        api_module = manager.create_module({
            'name': '测试API模块',
            'description': '测试模块管理器功能',
            'module_type': 'api',
            'status': 'planning',
            'version': '1.0.0',
            'author': 'Test Team'
        })
        if not api_module:
            return False
        
        # 测试添加依赖
        from scripts.vibe_coding.module_manager import ModuleDependency
        manager.add_module_dependency(api_module.module_id, ModuleDependency(
            module_id='module_test_service',
            version='1.0.0',
            dependency_type='runtime'
        ))
        
        # 测试添加接口
        from scripts.vibe_coding.module_manager import ModuleInterface
        manager.add_module_interface(api_module.module_id, ModuleInterface(
            interface_id='test_api_interface',
            name='测试API接口',
            description='测试API接口功能',
            inputs={'test': 'string'}, 
            outputs={'result': 'boolean'},
            methods=['GET', 'POST']
        ))
        
        # 测试更新模块状态
        from scripts.vibe_coding.module_manager import ModuleStatus
        manager.update_module_status(api_module.module_id, ModuleStatus.DEVELOPING)
        
        # 测试列出模块
        modules = manager.list_modules()
        if not modules:
            return False
        
        # 测试分析依赖
        dependency_analysis = manager.analyze_dependencies(api_module.module_id)
        if not dependency_analysis:
            return False
        
        # 测试生成模块结构
        structure = manager.generate_module_structure(api_module.module_id)
        if not structure:
            return False
        
        print(f"   模块创建成功: {api_module.module_id}")
        print(f"   依赖添加成功")
        print(f"   接口添加成功")
        print(f"   状态更新成功")
        print(f"   模块列出成功: {len(modules)} 个模块")
        print(f"   依赖分析成功")
        print(f"   模块结构生成成功")
        
        return True
    
    def test_multimodal_processor(self):
        """测试多模态处理器"""
        print("测试多模态处理器...")
        processor = MultimodalProcessor(storage_path=".")
        
        # 测试文本到代码转换
        text = "创建一个函数，处理用户列表，打印每个用户的姓名、邮箱和电话"
        code_result = processor.convert_text_to_code(text, language="python")
        if not code_result:
            return False
        
        # 测试文本到JavaScript代码转换
        js_result = processor.convert_text_to_code(text, language="javascript")
        if not js_result:
            return False
        
        # 测试获取处理历史
        history = processor.get_processing_history()
        if not history:
            return False
        
        print(f"   Python代码转换成功")
        print(f"   JavaScript代码转换成功")
        print(f"   处理历史获取成功: {len(history)} 条记录")
        
        return True
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始 Vibe Coding 功能测试")
        print("=" * 60)
        
        # 运行各个模块的测试
        self.run_test("规划引擎测试", self.test_planning_engine)
        self.run_test("提示词进化系统测试", self.test_prompt_evolution)
        self.run_test("增强上下文管理器测试", self.test_enhanced_context_manager)
        self.run_test("模块管理器测试", self.test_module_manager)
        self.run_test("多模态处理器测试", self.test_multimodal_processor)
        
        # 显示测试结果
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("-" * 60)
        print(f"总测试数: {self.test_count}")
        print(f"通过: {self.passed_count}")
        print(f"失败: {self.failed_count}")
        print(f"成功率: {self.passed_count / self.test_count * 100:.1f}%")
        
        # 显示失败的测试
        if self.failed_count > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if result['status'] != 'passed':
                    print(f"- {result['name']}: {result['status']} - {result['message']}")
        
        # 保存测试结果
        self.save_test_results()
        
        return self.failed_count == 0
    
    def save_test_results(self):
        """保存测试结果"""
        import json
        import datetime
        
        results_dir = Path(".") / "test_results"
        results_dir.mkdir(exist_ok=True)
        
        test_result = {
            'timestamp': datetime.datetime.now().isoformat(),
            'total_tests': self.test_count,
            'passed_tests': self.passed_count,
            'failed_tests': self.failed_count,
            'success_rate': self.passed_count / self.test_count * 100 if self.test_count > 0 else 0,
            'results': self.test_results
        }
        
        result_file = results_dir / f"vibe_coding_test_{int(time.time())}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n测试结果已保存到: {result_file}")

if __name__ == "__main__":
    """运行测试"""
    tester = VibeCodingTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 有测试失败！")
        sys.exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae Multi-Agent v2.0 综合测试和示例

测试所有新组件的功能：
1. 双层上下文管理器
2. 技能注册中心
3. 角色匹配器
4. 工作流引擎
"""

import sys
from pathlib import Path

# 添加脚本目录到路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))


def test_dual_layer_context_manager():
    """测试双层上下文管理器"""
    print("\n" + "="*80)
    print("测试双层上下文管理器")
    print("="*80)
    
    from dual_layer_context_manager import (
        DualLayerContextManager,
        TaskDefinition,
        UserProfile
    )
    
    # 创建管理器
    manager = DualLayerContextManager(
        project_root=".",
        skill_root=str(script_dir.parent)
    )
    
    # 初始化用户画像
    manager.global_context.set_user_profile(
        UserProfile(
            user_id="test-user",
            identity="架构师",
            preferences={"language": "zh", "detail_level": "high"},
            expertise=["Java", "Spring Boot", "微服务"]
        )
    )
    print("✅ 用户画像已设置")
    
    # 开始任务 1
    task_def1 = TaskDefinition(
        task_id="TEST-001",
        title="设计微服务架构",
        description="设计一个高可用的微服务架构",
        goals=["高可用", "可扩展"],
        constraints=["Java 21", "Spring Boot 3"]
    )
    
    task_ctx1 = manager.start_task(task_def1)
    print("✅ 任务 1 已启动")
    
    # 添加思考
    task_ctx1.add_thought(
        role="architect",
        thought_type="analysis",
        content="考虑到系统需要高可用，建议采用微服务架构",
        context={"alternatives": ["单体架构", "SOA"]}
    )
    
    # 添加工件
    task_ctx1.add_artifact("ARCHITECTURE", {
        "style": "微服务",
        "components": ["API Gateway", "Service Registry", "Config Server"]
    })
    print("✅ 工件已添加")
    
    # 完成任务 1
    manager.complete_task("TEST-001")
    print("✅ 任务 1 已完成，经验已沉淀")
    
    # 开始任务 2（应该能获取到任务 1 的经验）
    task_def2 = TaskDefinition(
        task_id="TEST-002",
        title="实现用户服务",
        description="实现用户管理微服务",
        goals=["用户 CRUD", "权限管理"]
    )
    
    task_ctx2 = manager.start_task(task_def2)
    print("✅ 任务 2 已启动，相关知识已注入")
    
    # 完成任务 2
    manager.complete_task("TEST-002")
    print("✅ 任务 2 已完成")
    
    # 显示统计
    stats = manager.get_statistics()
    print(f"\n📊 统计信息:")
    print(f"  全局上下文版本：{stats['global_context']['version']}")
    print(f"  知识库条目：{stats['global_context']['knowledge_count']}")
    print(f"  经验库条目：{stats['global_context']['experience_count']}")
    print(f"  任务上下文数：{stats['task_contexts']}")
    
    return True


def test_skill_registry():
    """测试技能注册中心"""
    print("\n" + "="*80)
    print("测试技能注册中心")
    print("="*80)
    
    from skill_registry import SkillRegistry, SkillManifest, SkillCapability
    
    # 创建注册中心
    registry = SkillRegistry(registry_path=str(script_dir.parent))
    
    # 注册技能
    manifest = SkillManifest(
        name="test-skill",
        version="1.0.0",
        description="测试技能",
        author="Test Team",
        capabilities=[
            SkillCapability(
                name="test-capability",
                description="测试能力",
                input_schema={"type": "object"},
                output_schema={"type": "object"}
            )
        ]
    )
    
    registry.register(manifest)
    print("✅ 技能已注册")
    
    # 获取技能
    skill = registry.get_skill("test-skill")
    if skill:
        print(f"✅ 获取技能：{skill.name} v{skill.version}")
    
    # 列出技能
    skills = registry.list_skills()
    print(f"✅ 技能总数：{len(skills)}")
    
    # 显示统计
    stats = registry.get_statistics()
    print(f"\n📊 统计信息:")
    print(f"  总技能数：{stats['total_skills']}")
    print(f"  活跃技能：{stats['active_skills']}")
    print(f"  总能力数：{stats['total_capabilities']}")
    
    return True


def test_role_matcher():
    """测试角色匹配器"""
    print("\n" + "="*80)
    print("测试角色匹配器")
    print("="*80)
    
    from role_matcher import RoleMatcher, TaskRequirement, create_default_roles
    
    # 创建匹配器
    matcher = RoleMatcher()
    
    # 注册默认角色
    roles = create_default_roles()
    for role in roles:
        matcher.register_role(role)
    print(f"✅ 已注册 {len(roles)} 个角色")
    
    # 创建任务需求
    requirement = TaskRequirement(
        task_id="MATCH-TEST-001",
        title="设计数据库架构",
        description="设计一个支持高并发的数据库架构",
        required_capabilities=["系统架构设计", "技术选型"],
        preferred_skills=["架构设计", "数据库"]
    )
    
    # 匹配角色
    results = matcher.match(requirement, top_k=3)
    print(f"\n🎯 任务：{requirement.title}")
    print(f"✅ 匹配到 {len(results)} 个角色:")
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.role_name} ({result.role_id})")
        print(f"   置信度：{result.confidence:.2%}")
        if result.reasons:
            print(f"   匹配原因:")
            for reason in result.reasons[:2]:
                print(f"   - {reason}")
    
    # 建议工作流
    workflow = matcher.suggest_workflow(requirement)
    print(f"\n📋 建议工作流:")
    for i, role_id in enumerate(workflow[:4], 1):
        role = matcher.roles.get(role_id)
        role_name = role.name if role else role_id
        print(f"{i}. {role_name}")
    
    return True


def test_workflow_engine():
    """测试工作流引擎"""
    print("\n" + "="*80)
    print("测试工作流引擎")
    print("="*80)
    
    from workflow_engine import WorkflowEngine
    
    # 创建引擎
    engine = WorkflowEngine(storage_path=str(script_dir.parent))
    
    # 创建默认工作流
    engine.create_default_workflows()
    print(f"✅ 已创建 {len(engine.definitions)} 个工作流")
    
    # 列出工作流
    definitions = engine.list_definitions()
    print(f"\n📋 工作流列表:")
    for definition in definitions:
        print(f"  - {definition.name} ({definition.workflow_id})")
        print(f"    步骤数：{len(definition.steps)}")
    
    # 注册执行器
    def mock_executor(step, inputs, instance):
        print(f"    ▶️  执行：{step.name}")
        return {"status": "success", "step": step.step_id}
    
    for action in ["analyze_requirements", "design_architecture", 
                   "implement_code", "execute_tests", "rapid_implementation"]:
        engine.register_executor(action, mock_executor)
    print(f"\n✅ 已注册 {len(engine.executors)} 个执行器")
    
    # 启动工作流
    print(f"\n🚀 启动工作流：standard-dev-workflow")
    instance = engine.start_workflow(
        "standard-dev-workflow",
        variables={"detail_level": "high"}
    )
    
    if instance:
        # 获取进度
        progress = engine.get_progress(instance.instance_id)
        print(f"\n📊 进度:")
        print(f"  状态：{progress['status']}")
        print(f"  完成：{progress['completed']}/{progress['total_steps']}")
        print(f"  进度：{progress['progress']:.1%}")
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*80)
    print("Trae Multi-Agent v2.0 综合测试")
    print("="*80)
    
    tests = [
        ("双层上下文管理器", test_dual_layer_context_manager),
        ("技能注册中心", test_skill_registry),
        ("角色匹配器", test_role_matcher),
        ("工作流引擎", test_workflow_engine)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = "✅ 通过" if success else "❌ 失败"
        except Exception as e:
            results[test_name] = f"❌ 错误：{e}"
            import traceback
            traceback.print_exc()
    
    # 显示总结果
    print("\n" + "="*80)
    print("测试总结果")
    print("="*80)
    
    for test_name, result in results.items():
        print(f"{test_name}: {result}")
    
    # 统计
    passed = sum(1 for r in results.values() if r.startswith("✅"))
    total = len(tests)
    
    print(f"\n总计：{passed}/{total} 个测试通过")
    
    return passed == total


def main():
    """主函数"""
    success = run_all_tests()
    
    if success:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())

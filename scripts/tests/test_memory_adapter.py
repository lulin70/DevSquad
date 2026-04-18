#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Adapter 测试脚本

测试 Memory Classification Engine 与 DevSquad 的集成
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_adapter import (
    MemoryAdapter, MemoryType, MemoryTier, 
    MemoryTypeMapper, MemoryItem, memory_adapter
)

def test_memory_type_mapper():
    """测试记忆类型分类器"""
    print("=" * 60)
    print("测试 1: MemoryTypeMapper 分类准确性")
    print("=" * 60)
    
    mapper = MemoryTypeMapper()
    
    test_cases = [
        ("我喜欢使用 Python 进行开发", MemoryType.USER_PREFERENCE),
        ("我不喜欢在代码中使用破折号", MemoryType.USER_PREFERENCE),
        ("不对，应该是用 TypeScript", MemoryType.CORRECTION),
        ("错了，这个方案不可行", MemoryType.CORRECTION),
        ("我们公司有 50 名员工", MemoryType.FACT_DECLARATION),
        ("我是架构师", MemoryType.FACT_DECLARATION),
        ("决定采用微服务架构", MemoryType.DECISION),
        ("最终方案确定使用 React", MemoryType.DECISION),
        ("张三是项目负责人", MemoryType.RELATIONSHIP),
        ("李四负责前端开发", MemoryType.RELATIONSHIP),
        ("通常我们会先做技术选型", MemoryType.TASK_PATTERN),
        ("一般流程是先设计后开发", MemoryType.TASK_PATTERN),
        ("这个方案太棒了", MemoryType.SENTIMENT_MARKER),
        ("非常满意这个结果", MemoryType.SENTIMENT_MARKER),
    ]
    
    correct = 0
    total = len(test_cases)
    
    for message, expected_type in test_cases:
        mem_type, confidence = mapper.classify_message(message)
        tier = mapper.determine_tier(mem_type)
        
        is_correct = mem_type == expected_type
        status = "✅" if is_correct else "❌"
        
        if is_correct:
            correct += 1
        
        print(f"\n{status} 消息: {message[:30]}...")
        print(f"   预期: {expected_type.value}")
        print(f"   实际: {mem_type.value}")
        print(f"   置信度: {confidence:.2f}")
        print(f"   层级: {tier.value}")
    
    accuracy = correct / total * 100
    print(f"\n{'=' * 60}")
    print(f"分类准确率: {correct}/{total} = {accuracy:.1f}%")
    print(f"{'=' * 60}")
    
    return accuracy >= 70

def test_memory_adapter():
    """测试记忆适配器核心功能"""
    print("\n" + "=" * 60)
    print("测试 2: MemoryAdapter 核心功能")
    print("=" * 60)
    
    adapter = MemoryAdapter()
    
    print("\n2.1 测试 process_message()")
    test_messages = [
        "我喜欢使用 Python 进行开发",
        "决定采用微服务架构",
        "张三是项目负责人",
    ]
    
    processed = []
    for msg in test_messages:
        result = adapter.process_message(msg)
        if result:
            processed.append(result)
            print(f"  ✅ 处理成功: {msg[:30]}...")
            print(f"     类型: {result.memory_type.value}, 层级: {result.tier.value}")
        else:
            print(f"  ⚠️  未识别为记忆: {msg[:30]}...")
    
    print(f"\n2.2 测试 retrieve_memories()")
    query = "开发"
    memories = adapter.retrieve_memories(query, limit=5)
    print(f"  查询: '{query}'")
    print(f"  结果: {len(memories)} 条记忆")
    for m in memories:
        print(f"    - {m.content[:40]}... (类型: {m.memory_type.value})")
    
    print(f"\n2.3 测试 get_statistics()")
    stats = adapter.get_statistics()
    print(f"  总记忆数: {stats['total_memories']}")
    print(f"  按层级: {stats['by_tier']}")
    print(f"  按类型: {stats['by_type']}")
    print(f"  MCE 启用: {stats['mce_enabled']}")
    
    print(f"\n2.4 测试 apply_forgetting()")
    forgotten = adapter.apply_forgetting(decay_factor=0.9, min_weight=0.1)
    print(f"  遗忘记忆数: {forgotten}")
    
    return True

def test_tier_mapping():
    """测试层级映射"""
    print("\n" + "=" * 60)
    print("测试 3: 记忆类型到层级的映射")
    print("=" * 60)
    
    mapper = MemoryTypeMapper()
    
    expected_mappings = {
        MemoryType.USER_PREFERENCE: MemoryTier.TIER_2_PROCEDURAL,
        MemoryType.CORRECTION: MemoryTier.TIER_2_PROCEDURAL,
        MemoryType.FACT_DECLARATION: MemoryTier.TIER_4_SEMANTIC,
        MemoryType.DECISION: MemoryTier.TIER_3_EPISODIC,
        MemoryType.RELATIONSHIP: MemoryTier.TIER_4_SEMANTIC,
        MemoryType.TASK_PATTERN: MemoryTier.TIER_3_EPISODIC,
        MemoryType.SENTIMENT_MARKER: MemoryTier.TIER_2_PROCEDURAL,
    }
    
    correct = 0
    total = len(expected_mappings)
    
    for mem_type, expected_tier in expected_mappings.items():
        actual_tier = mapper.determine_tier(mem_type)
        is_correct = actual_tier == expected_tier
        status = "✅" if is_correct else "❌"
        
        if is_correct:
            correct += 1
        
        print(f"  {status} {mem_type.value} → {actual_tier.value} (预期: {expected_tier.value})")
    
    accuracy = correct / total * 100
    print(f"\n层级映射准确率: {correct}/{total} = {accuracy:.1f}%")
    
    return accuracy == 100

def test_integration_with_context_manager():
    """测试与双层上下文管理器的集成"""
    print("\n" + "=" * 60)
    print("测试 4: 与 DualLayerContextManager 集成")
    print("=" * 60)
    
    try:
        from dual_layer_context_manager import DualLayerContextManager, TaskDefinition
        
        import tempfile
        _tmp = tempfile.gettempdir()
        manager = DualLayerContextManager(
            project_root=os.path.join(_tmp, "test_trae_project"),
            skill_root=os.path.join(_tmp, "test_trae_skill")
        )
        
        print(f"  Memory Adapter 集成状态: {manager._use_memory_adapter}")
        
        if manager._use_memory_adapter:
            print("\n  4.1 测试 process_message_with_memory()")
            result = manager.process_message_with_memory("我喜欢使用 Python 进行开发")
            if result:
                print(f"    ✅ 记忆已处理: {result.memory_type.value}")
            else:
                print(f"    ⚠️  未识别为记忆")
            
            print("\n  4.2 测试 get_memory_statistics()")
            stats = manager.get_memory_statistics()
            print(f"    总知识数: {stats['total_knowledge']}")
            print(f"    MCE 集成: {stats['mce_integration']}")
            
            print("\n  4.3 测试 apply_forgetting()")
            result = manager.apply_forgetting()
            print(f"    遗忘数: {result['forgotten_count']}")
            print(f"    剩余数: {result['remaining_count']}")
        else:
            print("  ⚠️  Memory Adapter 未启用，使用降级模式")
        
        return True
    except Exception as e:
        print(f"  ❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Memory Classification Engine 集成测试")
    print("=" * 60)
    
    results = []
    
    results.append(("MemoryTypeMapper 分类", test_memory_type_mapper()))
    results.append(("MemoryAdapter 功能", test_memory_adapter()))
    results.append(("层级映射", test_tier_mapping()))
    results.append(("上下文管理器集成", test_integration_with_context_manager()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

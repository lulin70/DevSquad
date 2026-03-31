#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding 增强上下文管理系统

基于双层上下文管理器，增强上下文管理功能和多模型协作能力。
"""

import os
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum
import copy

# 导入现有上下文管理系统
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from scripts.dual_layer_context_manager import (
    ContextLevel, SyncDirection, UserProfile, KnowledgeItem, ExperienceItem,
    CollaborationRecord, CapabilityModel, TaskDefinition, TaskStatus, ThoughtRecord,
    ContextSynchronizer, GlobalContext, TaskContext, DualLayerContextManager
)

class ModelType(Enum):
    """模型类型"""
    GENERAL = "general"  # 通用模型
    CODE = "code"        # 代码模型
    CHAT = "chat"        # 聊天模型
    VISION = "vision"    # 视觉模型
    AUDIO = "audio"      # 音频模型

class ModelCapability(Enum):
    """模型能力"""
    CODE_GENERATION = "code_generation"  # 代码生成
    CODE_ANALYSIS = "code_analysis"      # 代码分析
    NATURAL_LANGUAGE = "natural_language"  # 自然语言处理
    VISION_PROCESSING = "vision_processing"  # 视觉处理
    AUDIO_PROCESSING = "audio_processing"  # 音频处理
    PLANNING = "planning"  # 规划能力
    PROBLEM_SOLVING = "problem_solving"  # 问题解决

@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    model_type: ModelType
    name: str
    capabilities: List[ModelCapability]
    parameters: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ModelAssignment:
    """模型分配"""
    assignment_id: str
    task_id: str
    model_id: str
    capability: ModelCapability
    confidence: float
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    success: Optional[bool] = None

class EnhancedContextSynchronizer(ContextSynchronizer):
    """增强版上下文同步器"""
    
    def __init__(self):
        """初始化增强版同步器"""
        super().__init__()
        # 增加语义理解能力
        self.semantic_memory: Dict[str, Any] = {}
    
    def sync_task_to_global(self, global_ctx: 'EnhancedGlobalContext', 
                           task_ctx: 'EnhancedTaskContext',
                           task_id: str) -> Dict[str, Any]:
        """增强版任务到全局同步"""
        sync_result = super().sync_task_to_global(global_ctx, task_ctx, task_id)
        
        # 增加语义记忆同步
        semantic_updates = self._sync_semantic_memory(task_ctx)
        if semantic_updates:
            global_ctx.update_semantic_memory(semantic_updates)
            sync_result['updates'].extend([
                {'type': 'semantic_memory', 'action': 'updated'}
            ])
        
        return sync_result
    
    def sync_global_to_task(self, global_ctx: 'EnhancedGlobalContext',
                           task_ctx: 'EnhancedTaskContext',
                           task_definition: TaskDefinition) -> Dict[str, Any]:
        """增强版全局到任务同步"""
        sync_result = super().sync_global_to_task(global_ctx, task_ctx, task_definition)
        
        # 增加语义记忆注入
        semantic_memory = global_ctx.get_semantic_memory()
        if semantic_memory:
            relevant_memory = self._extract_relevant_semantic_memory(
                semantic_memory, task_definition
            )
            if relevant_memory:
                task_ctx.set_semantic_memory(relevant_memory)
                sync_result['injections'].append({
                    'type': 'semantic_memory',
                    'count': len(relevant_memory)
                })
        
        return sync_result
    
    def _sync_semantic_memory(self, task_ctx: 'EnhancedTaskContext') -> Dict[str, Any]:
        """同步语义记忆"""
        semantic_memory = task_ctx.get_semantic_memory()
        if semantic_memory:
            return semantic_memory
        return {}
    
    def _extract_relevant_semantic_memory(self, semantic_memory: Dict[str, Any],
                                         task_definition: TaskDefinition) -> Dict[str, Any]:
        """提取相关语义记忆"""
        # 简单的语义匹配（实际应该使用更复杂的语义理解）
        relevant_memory = {}
        task_text = f"{task_definition.title} {task_definition.description}"
        
        for key, value in semantic_memory.items():
            if key in task_text:
                relevant_memory[key] = value
        
        return relevant_memory

class EnhancedGlobalContext(GlobalContext):
    """增强版全局上下文"""
    
    def __init__(self, storage_path: str = "."):
        """初始化增强版全局上下文"""
        super().__init__(storage_path)
        # 增加语义记忆
        self.semantic_memory: Dict[str, Any] = {}
        # 增加模型管理
        self.models: Dict[str, ModelInfo] = {}
        # 增加模型分配历史
        self.model_assignments: Dict[str, ModelAssignment] = {}
    
    def _load(self):
        """加载数据"""
        super()._load()
        
        # 确保属性存在
        if not hasattr(self, 'semantic_memory'):
            self.semantic_memory = {}
        if not hasattr(self, 'models'):
            self.models = {}
        if not hasattr(self, 'model_assignments'):
            self.model_assignments = {}
        
        # 加载语义记忆和模型信息
        data_file = self.storage_path / "global_context.json"
        if data_file.exists():
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 恢复语义记忆
                self.semantic_memory = data.get('semantic_memory', {})
                
                # 恢复模型信息
                for m_id, m_data in data.get('models', {}).items():
                    model_type = ModelType(m_data['model_type'])
                    capabilities = [ModelCapability(c) for c in m_data['capabilities']]
                    self.models[m_id] = ModelInfo(
                        model_id=m_id,
                        model_type=model_type,
                        name=m_data['name'],
                        capabilities=capabilities,
                        parameters=m_data.get('parameters', {}),
                        performance=m_data.get('performance', {}),
                        usage_count=m_data.get('usage_count', 0)
                    )
                
                # 恢复模型分配历史
                for a_id, a_data in data.get('model_assignments', {}).items():
                    capability = ModelCapability(a_data['capability'])
                    self.model_assignments[a_id] = ModelAssignment(
                        assignment_id=a_id,
                        task_id=a_data['task_id'],
                        model_id=a_data['model_id'],
                        capability=capability,
                        confidence=a_data['confidence'],
                        created_at=a_data['created_at'],
                        completed_at=a_data.get('completed_at'),
                        success=a_data.get('success')
                    )
                    
            except Exception as e:
                print(f"加载增强全局上下文失败：{e}")
                # 确保属性存在
                self.semantic_memory = {}
                self.models = {}
                self.model_assignments = {}
    
    def _save(self):
        """保存数据"""
        # 先调用父类保存
        data_file = self.storage_path / "global_context.json"
        
        # 递增版本
        self.version += 1
        
        # 记录版本历史
        version_record = {
            'version': self.version,
            'timestamp': datetime.now().isoformat(),
            'stats': {
                'knowledge_count': len(self.knowledge_base),
                'experience_count': len(self.experience_db),
                'collaboration_count': len(self.collaboration_net),
                'model_count': len(self.models)
            }
        }
        self.version_history.append(version_record)
        
        # 保存数据
        data = {
            'version': self.version,
            'user_profile': asdict(self.user_profile) if self.user_profile else None,
            'knowledge_base': {k: asdict(v) for k, v in self.knowledge_base.items()},
            'experience_db': {k: asdict(v) for k, v in self.experience_db.items()},
            'collaboration_net': {k: asdict(v) for k, v in self.collaboration_net.items()},
            'capability_models': {k: asdict(v) for k, v in self.capability_models.items()},
            'semantic_memory': self.semantic_memory,
            'models': {
                k: {
                    'model_type': v.model_type.value,
                    'name': v.name,
                    'capabilities': [c.value for c in v.capabilities],
                    'parameters': v.parameters,
                    'performance': v.performance,
                    'usage_count': v.usage_count
                } for k, v in self.models.items()
            },
            'model_assignments': {
                k: {
                    'task_id': v.task_id,
                    'model_id': v.model_id,
                    'capability': v.capability.value,
                    'confidence': v.confidence,
                    'created_at': v.created_at,
                    'completed_at': v.completed_at,
                    'success': v.success
                } for k, v in self.model_assignments.items()
            },
            'version_history': self.version_history[-100:]
        }
        
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存增强全局上下文失败：{e}")
    
    def update_semantic_memory(self, semantic_memory: Dict[str, Any]):
        """更新语义记忆"""
        self.semantic_memory.update(semantic_memory)
        self._save()
    
    def get_semantic_memory(self) -> Dict[str, Any]:
        """获取语义记忆"""
        return self.semantic_memory
    
    def add_model(self, model: ModelInfo):
        """添加模型"""
        self.models[model.model_id] = model
        self._save()
    
    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """获取模型"""
        return self.models.get(model_id)
    
    def list_models(self) -> List[ModelInfo]:
        """列出所有模型"""
        return list(self.models.values())
    
    def add_model_assignment(self, assignment: ModelAssignment):
        """添加模型分配"""
        self.model_assignments[assignment.assignment_id] = assignment
        # 更新模型使用次数
        if assignment.model_id in self.models:
            self.models[assignment.model_id].usage_count += 1
        self._save()
    
    def get_model_assignments(self, task_id: str = None) -> List[ModelAssignment]:
        """获取模型分配"""
        if task_id:
            return [a for a in self.model_assignments.values() if a.task_id == task_id]
        return list(self.model_assignments.values())

class EnhancedTaskContext(TaskContext):
    """增强版任务上下文"""
    
    def __init__(self, task_id: str, storage_path: str = "."):
        """初始化增强版任务上下文"""
        super().__init__(task_id, storage_path)
        # 增加语义记忆
        self.semantic_memory: Dict[str, Any] = {}
        # 增加模型分配
        self.model_assignments: List[ModelAssignment] = []
    
    def _load(self):
        """加载数据"""
        super()._load()
        
        # 加载语义记忆和模型分配
        data_file = self.storage_path / "task_context.json"
        if data_file.exists():
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 恢复语义记忆
                self.semantic_memory = data.get('semantic_memory', {})
                
                # 恢复模型分配
                for a_data in data.get('model_assignments', []):
                    capability = ModelCapability(a_data['capability'])
                    assignment = ModelAssignment(
                        assignment_id=a_data['assignment_id'],
                        task_id=a_data['task_id'],
                        model_id=a_data['model_id'],
                        capability=capability,
                        confidence=a_data['confidence'],
                        created_at=a_data['created_at'],
                        completed_at=a_data.get('completed_at'),
                        success=a_data.get('success')
                    )
                    self.model_assignments.append(assignment)
                    
            except Exception as e:
                print(f"加载增强任务上下文失败：{e}")
    
    def _save(self):
        """保存数据"""
        data_file = self.storage_path / "task_context.json"
        
        data = {
            'task_id': self.task_id,
            'definition': asdict(self.definition) if self.definition else None,
            'status': asdict(self.status) if self.status else None,
            'working_memory': self.working_memory,
            'artifacts': self.artifacts,
            'thoughts': [asdict(t) for t in self.thoughts],
            'references': {
                'knowledge': [asdict(k) for k in self.knowledge_references],
                'experience': [asdict(e) for e in self.experience_references]
            },
            'user_preferences': self.user_preferences,
            'semantic_memory': self.semantic_memory,
            'model_assignments': [
                {
                    'assignment_id': a.assignment_id,
                    'task_id': a.task_id,
                    'model_id': a.model_id,
                    'capability': a.capability.value,
                    'confidence': a.confidence,
                    'created_at': a.created_at,
                    'completed_at': a.completed_at,
                    'success': a.success
                } for a in self.model_assignments
            ]
        }
        
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存增强任务上下文失败：{e}")
    
    def set_semantic_memory(self, semantic_memory: Dict[str, Any]):
        """设置语义记忆"""
        self.semantic_memory = semantic_memory
        self._save()
    
    def get_semantic_memory(self) -> Dict[str, Any]:
        """获取语义记忆"""
        return self.semantic_memory
    
    def add_model_assignment(self, assignment: ModelAssignment):
        """添加模型分配"""
        self.model_assignments.append(assignment)
        self._save()
    
    def get_model_assignments(self) -> List[ModelAssignment]:
        """获取模型分配"""
        return self.model_assignments

class ModelCoordinator:
    """模型协调器"""
    
    def __init__(self, global_context: EnhancedGlobalContext):
        """初始化模型协调器"""
        self.global_context = global_context
    
    def assign_model(self, task_id: str, capability: ModelCapability) -> Optional[ModelAssignment]:
        """
        为任务分配模型
        
        Args:
            task_id: 任务 ID
            capability: 需要的模型能力
        
        Returns:
            ModelAssignment: 模型分配
        """
        # 查找具备所需能力的模型
        suitable_models = []
        for model_id, model in self.global_context.models.items():
            if capability in model.capabilities:
                # 计算匹配度（可以根据更多因素）
                confidence = self._calculate_confidence(model, capability)
                suitable_models.append((model_id, model, confidence))
        
        # 按匹配度排序
        suitable_models.sort(key=lambda x: x[2], reverse=True)
        
        if not suitable_models:
            return None
        
        # 选择最佳模型
        best_model_id, best_model, confidence = suitable_models[0]
        
        # 创建模型分配
        assignment = ModelAssignment(
            assignment_id=f"assignment_{int(time.time())}",
            task_id=task_id,
            model_id=best_model_id,
            capability=capability,
            confidence=confidence
        )
        
        # 保存模型分配
        self.global_context.add_model_assignment(assignment)
        
        return assignment
    
    def _calculate_confidence(self, model: ModelInfo, capability: ModelCapability) -> float:
        """计算模型匹配度"""
        # 基础匹配度
        confidence = 0.7
        
        # 根据模型类型调整
        if model.model_type == ModelType.CODE and capability in [
            ModelCapability.CODE_GENERATION, ModelCapability.CODE_ANALYSIS
        ]:
            confidence += 0.2
        elif model.model_type == ModelType.VISION and capability == ModelCapability.VISION_PROCESSING:
            confidence += 0.2
        elif model.model_type == ModelType.AUDIO and capability == ModelCapability.AUDIO_PROCESSING:
            confidence += 0.2
        
        # 根据使用次数调整（使用次数越多，信心越高）
        usage_bonus = min(model.usage_count / 100, 0.1)
        confidence += usage_bonus
        
        return min(confidence, 1.0)
    
    def update_assignment_status(self, assignment_id: str, success: bool):
        """更新分配状态"""
        if assignment_id in self.global_context.model_assignments:
            assignment = self.global_context.model_assignments[assignment_id]
            assignment.success = success
            assignment.completed_at = datetime.now().isoformat()
            self.global_context._save()
    
    def get_best_model(self, capability: ModelCapability) -> Optional[ModelInfo]:
        """获取最佳模型"""
        suitable_models = []
        for model_id, model in self.global_context.models.items():
            if capability in model.capabilities:
                confidence = self._calculate_confidence(model, capability)
                suitable_models.append((model, confidence))
        
        if not suitable_models:
            return None
        
        suitable_models.sort(key=lambda x: x[1], reverse=True)
        return suitable_models[0][0]

class EnhancedDualLayerContextManager(DualLayerContextManager):
    """增强版双层上下文管理器"""
    
    def __init__(self, project_root: str = ".", skill_root: str = "."):
        """初始化增强版上下文管理器"""
        # 重写父类初始化，使用增强版上下文
        self.project_root = Path(project_root)
        self.skill_root = Path(skill_root)
        
        # 双层上下文
        self.global_context = EnhancedGlobalContext(str(self.skill_root))
        self.task_contexts: Dict[str, EnhancedTaskContext] = {}
        
        # 同步器
        self.synchronizer = EnhancedContextSynchronizer()
        
        # 模型协调器
        self.model_coordinator = ModelCoordinator(self.global_context)
        
        # 当前任务
        self.current_task_id: Optional[str] = None
        
        # 初始化项目结构
        self._ensure_project_structure()
    
    def start_task(self, task_definition: TaskDefinition) -> EnhancedTaskContext:
        """开始新任务"""
        task_id = task_definition.task_id
        
        # 创建增强版任务上下文
        task_ctx = EnhancedTaskContext(task_id, str(self.skill_root))
        task_ctx.set_definition(task_definition)
        
        # 从全局上下文注入相关知识
        self.synchronizer.sync_global_to_task(
            self.global_context,
            task_ctx,
            task_definition
        )
        
        # 保存任务上下文
        self.task_contexts[task_id] = task_ctx
        self.current_task_id = task_id
        
        print(f"✅ 增强版任务 {task_id} 已启动，相关知识已注入")
        return task_ctx
    
    def complete_task(self, task_id: str) -> bool:
        """完成任务"""
        if task_id not in self.task_contexts:
            print(f"❌ 任务不存在：{task_id}")
            return False
        
        task_ctx = self.task_contexts[task_id]
        
        # 更新任务状态
        task_ctx.update_status(status='completed')
        
        # 将经验沉淀到全局上下文
        sync_result = self.synchronizer.sync_task_to_global(
            self.global_context,
            task_ctx,
            task_id
        )
        
        print(f"✅ 任务 {task_id} 已完成，经验已沉淀")
        print(f"   同步更新：{len(sync_result['updates'])} 项")
        
        return True
    
    def assign_model(self, task_id: str, capability: ModelCapability) -> Optional[ModelAssignment]:
        """为任务分配模型"""
        if task_id not in self.task_contexts:
            print(f"❌ 任务不存在：{task_id}")
            return None
        
        # 分配模型
        assignment = self.model_coordinator.assign_model(task_id, capability)
        
        if assignment:
            # 将分配添加到任务上下文
            task_ctx = self.task_contexts[task_id]
            task_ctx.add_model_assignment(assignment)
            print(f"✅ 为任务 {task_id} 分配模型：{assignment.model_id} (信心: {assignment.confidence:.2f})")
        
        return assignment
    
    def get_current_context(self) -> Optional[EnhancedTaskContext]:
        """获取当前任务上下文"""
        if self.current_task_id and self.current_task_id in self.task_contexts:
            return self.task_contexts[self.current_task_id]
        return None
    
    def get_global_context(self) -> EnhancedGlobalContext:
        """获取全局上下文"""
        return self.global_context
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'global_context': {
                'version': self.global_context.get_version(),
                'knowledge_count': len(self.global_context.knowledge_base),
                'experience_count': len(self.global_context.experience_db),
                'collaboration_count': len(self.global_context.collaboration_net),
                'model_count': len(self.global_context.models)
            },
            'task_contexts': len(self.task_contexts),
            'current_task': self.current_task_id,
            'sync_history_count': len(self.synchronizer.sync_history)
        }

if __name__ == '__main__':
    """示例用法"""
    # 创建增强版上下文管理器
    manager = EnhancedDualLayerContextManager(
        project_root=".",
        skill_root="."
    )
    
    # 初始化用户画像
    manager.global_context.set_user_profile(
        UserProfile(
            user_id="default",
            identity="架构师",
            preferences={"language": "zh", "detail_level": "high"},
            expertise=["Java", "Spring Boot", "微服务"]
        )
    )
    
    # 添加模型
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
    
    manager.global_context.add_model(ModelInfo(
        model_id="code-davinci-002",
        model_type=ModelType.CODE,
        name="Code Davinci",
        capabilities=[
            ModelCapability.CODE_GENERATION,
            ModelCapability.CODE_ANALYSIS
        ]
    ))
    
    # 开始新任务
    task_def = TaskDefinition(
        task_id="TASK-001",
        title="设计系统架构",
        description="设计一个微服务架构",
        goals=["高可用", "可扩展", "易维护"],
        constraints=["Java 21", "Spring Boot 3"]
    )
    
    task_ctx = manager.start_task(task_def)
    
    # 分配模型
    manager.assign_model("TASK-001", ModelCapability.PLANNING)
    
    # 添加思考记录
    task_ctx.add_thought(
        role="architect",
        thought_type="analysis",
        content="考虑到系统需要高可用，建议采用微服务架构",
        context={"alternatives": ["单体架构", "SOA"]}
    )
    
    # 添加工件
    task_ctx.add_artifact("ARCHITECTURE", {
        "style": "微服务",
        "components": ["API Gateway", "Service Registry", "Config Server"]
    })
    
    # 完成任务
    manager.complete_task("TASK-001")
    
    # 显示统计
    stats = manager.get_statistics()
    print(f"\n📊 增强版统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记忆适配器 - 连接 Memory Classification Engine 与 MultiAgentSkill

将 Memory Classification Engine 的 7 种记忆类型和 4 层存储架构
集成到 MultiAgentSkill 的双层上下文管理系统中。

记忆类型映射：
- user_preference → UserProfile.preferences
- correction → 系统行为纠正记录
- fact_declaration → KnowledgeItem (category: fact)
- decision → ExperienceItem.lessons_learned
- relationship → CollaborationRecord
- task_pattern → ExperienceItem.patterns
- sentiment_marker → 用户情感标记

存储层级映射：
- Tier 1 (工作记忆) → TaskContext (工作记忆)
- Tier 2 (程序性记忆) → GlobalContext.user_profile + 系统提示词
- Tier 3 (情节记忆) → GlobalContext.experiences + 向量检索
- Tier 4 (语义记忆) → GlobalContext.knowledge_base + 知识图谱
"""

import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 
                                    'memory-classification-engine', 'src'))
    from memory_classification_engine import MemoryClassificationEngine
    from memory_classification_engine.utils.config import ConfigManager
    MCE_AVAILABLE = True
except ImportError:
    MCE_AVAILABLE = False
    print("⚠️  Memory Classification Engine 不可用，使用内置简化实现")


class MemoryType(Enum):
    USER_PREFERENCE = "user_preference"
    CORRECTION = "correction"
    FACT_DECLARATION = "fact_declaration"
    DECISION = "decision"
    RELATIONSHIP = "relationship"
    TASK_PATTERN = "task_pattern"
    SENTIMENT_MARKER = "sentiment_marker"


class MemoryTier(Enum):
    TIER_1_WORKING = "tier_1"
    TIER_2_PROCEDURAL = "tier_2"
    TIER_3_EPISODIC = "tier_3"
    TIER_4_SEMANTIC = "tier_4"


@dataclass
class MemoryItem:
    memory_id: str
    memory_type: MemoryType
    tier: MemoryTier
    content: str
    confidence: float = 1.0
    source: str = ""
    tags: List[str] = field(default_factory=list)
    weight: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryTypeMapper:
    
    TYPE_TO_TIER_MAPPING = {
        MemoryType.USER_PREFERENCE: MemoryTier.TIER_2_PROCEDURAL,
        MemoryType.CORRECTION: MemoryTier.TIER_2_PROCEDURAL,
        MemoryType.FACT_DECLARATION: MemoryTier.TIER_4_SEMANTIC,
        MemoryType.DECISION: MemoryTier.TIER_3_EPISODIC,
        MemoryType.RELATIONSHIP: MemoryTier.TIER_4_SEMANTIC,
        MemoryType.TASK_PATTERN: MemoryTier.TIER_3_EPISODIC,
        MemoryType.SENTIMENT_MARKER: MemoryTier.TIER_2_PROCEDURAL,
    }
    
    TYPE_TO_DESCRIPTION = {
        MemoryType.USER_PREFERENCE: "用户明确表达的喜好、习惯、风格要求",
        MemoryType.CORRECTION: "用户纠正AI的判断或输出",
        MemoryType.FACT_DECLARATION: "用户陈述的关于自身或业务的事实",
        MemoryType.DECISION: "对话中达成的明确结论或选择",
        MemoryType.RELATIONSHIP: "涉及人物、团队、组织之间的关系",
        MemoryType.TASK_PATTERN: "反复出现的任务类型及其处理方式",
        MemoryType.SENTIMENT_MARKER: "用户对某话题的明确情感倾向",
    }
    
    @classmethod
    def determine_tier(cls, memory_type: MemoryType) -> MemoryTier:
        return cls.TYPE_TO_TIER_MAPPING.get(memory_type, MemoryTier.TIER_3_EPISODIC)
    
    @classmethod
    def classify_message(cls, message: str) -> Tuple[MemoryType, float]:
        message_lower = message.lower()
        
        preference_patterns = [
            '我喜欢', '我不喜欢', '我偏好', '我希望', '我习惯',
            'i prefer', 'i like', 'i want', 'my preference'
        ]
        for pattern in preference_patterns:
            if pattern in message_lower:
                return MemoryType.USER_PREFERENCE, 0.9
        
        correction_patterns = [
            '不对', '错了', '不是这样', '应该是', '纠正',
            'wrong', 'incorrect', 'should be', 'correction'
        ]
        for pattern in correction_patterns:
            if pattern in message_lower:
                return MemoryType.CORRECTION, 0.85
        
        fact_patterns = [
            '我是', '我们公司', '我的团队', '我们的项目',
            'i am', 'my company', 'my team', 'our project'
        ]
        for pattern in fact_patterns:
            if pattern in message_lower:
                return MemoryType.FACT_DECLARATION, 0.8
        
        decision_patterns = [
            '决定', '选择', '确定', '就这个了', '最终方案',
            'decided', 'chosen', 'final decision', 'we will'
        ]
        for pattern in decision_patterns:
            if pattern in message_lower:
                return MemoryType.DECISION, 0.85
        
        relationship_patterns = [
            '和...合作', '负责', '领导', '汇报给', '同事',
            'collaborate with', 'responsible for', 'reports to', 'colleague'
        ]
        for pattern in relationship_patterns:
            if pattern in message_lower:
                return MemoryType.RELATIONSHIP, 0.75
        
        task_patterns = [
            '通常这样', '一般流程', '标准做法', '惯例',
            'usually', 'standard process', 'typical approach'
        ]
        for pattern in task_patterns:
            if pattern in message_lower:
                return MemoryType.TASK_PATTERN, 0.7
        
        sentiment_patterns = [
            '太棒了', '很糟糕', '非常满意', '很不满意',
            'great', 'terrible', 'satisfied', 'unsatisfied'
        ]
        for pattern in sentiment_patterns:
            if pattern in message_lower:
                return MemoryType.SENTIMENT_MARKER, 0.8
        
        return MemoryType.FACT_DECLARATION, 0.5


class MemoryAdapter:
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self.type_mapper = MemoryTypeMapper()
        
        self._local_memories: Dict[str, List[MemoryItem]] = {
            tier.value: [] for tier in MemoryTier
        }
        
        if MCE_AVAILABLE:
            try:
                self.mce_engine = MemoryClassificationEngine(config_path)
                self._use_mce = True
            except Exception as e:
                print(f"⚠️  MCE 初始化失败: {e}，使用本地模式")
                self.mce_engine = None
                self._use_mce = False
        else:
            self.mce_engine = None
            self._use_mce = False
    
    def process_message(self, message: str, context: Dict[str, Any] = None) -> Optional[MemoryItem]:
        if self._use_mce and self.mce_engine:
            return self._process_with_mce(message, context)
        else:
            return self._process_local(message, context)
    
    def _process_with_mce(self, message: str, context: Dict[str, Any] = None) -> Optional[MemoryItem]:
        try:
            result = self.mce_engine.process_message(message)
            if result and result.get('matched'):
                memory_type = MemoryType(result.get('memory_type', 'fact_declaration'))
                tier = MemoryTier(result.get('tier', 3))
                
                return MemoryItem(
                    memory_id=result.get('id', ''),
                    memory_type=memory_type,
                    tier=tier,
                    content=result.get('content', ''),
                    confidence=result.get('confidence', 1.0),
                    source=result.get('source', ''),
                    metadata={'raw_result': result}
                )
        except Exception as e:
            print(f"⚠️  MCE 处理失败: {e}")
            return self._process_local(message, context)
        
        return None
    
    def _process_local(self, message: str, context: Dict[str, Any] = None) -> Optional[MemoryItem]:
        memory_type, confidence = self.type_mapper.classify_message(message)
        tier = self.type_mapper.determine_tier(memory_type)
        
        if confidence < 0.5:
            return None
        
        memory_id = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(message) % 10000}"
        
        memory_item = MemoryItem(
            memory_id=memory_id,
            memory_type=memory_type,
            tier=tier,
            content=message,
            confidence=confidence,
            source="local_classifier",
            tags=self._extract_tags(message)
        )
        
        self._local_memories[tier.value].append(memory_item)
        
        return memory_item
    
    def _extract_tags(self, message: str) -> List[str]:
        tags = []
        
        tech_keywords = ['python', 'javascript', 'react', 'api', 'database', 
                        '架构', '测试', '部署', '代码', '功能']
        for keyword in tech_keywords:
            if keyword.lower() in message.lower():
                tags.append(keyword)
        
        return tags[:5]
    
    def retrieve_memories(self, query: str, tier: MemoryTier = None, 
                         memory_type: MemoryType = None, limit: int = 10) -> List[MemoryItem]:
        if self._use_mce and self.mce_engine:
            return self._retrieve_with_mce(query, tier, memory_type, limit)
        else:
            return self._retrieve_local(query, tier, memory_type, limit)
    
    def _retrieve_with_mce(self, query: str, tier: MemoryTier = None,
                          memory_type: MemoryType = None, limit: int = 10) -> List[MemoryItem]:
        try:
            results = self.mce_engine.retrieve_memories(query, limit=limit)
            
            memories = []
            for result in results:
                if isinstance(result, dict):
                    mem_type_str = result.get('memory_type', 'fact_declaration')
                    tier_str = result.get('tier', 'tier_3')
                else:
                    mem_type_str = getattr(result, 'memory_type', 'fact_declaration')
                    tier_str = getattr(result, 'tier', 'tier_3')
                
                try:
                    mem_type = MemoryType(mem_type_str) if isinstance(mem_type_str, str) else mem_type_str
                except ValueError:
                    mem_type = MemoryType.FACT_DECLARATION
                
                try:
                    result_tier = MemoryTier(tier_str) if isinstance(tier_str, str) else tier_str
                except ValueError:
                    result_tier = MemoryTier.TIER_3_EPISODIC
                
                if tier and result_tier != tier:
                    continue
                if memory_type and mem_type != memory_type:
                    continue
                
                content = result.get('content', '') if isinstance(result, dict) else str(result)
                
                memories.append(MemoryItem(
                    memory_id=result.get('id', '') if isinstance(result, dict) else str(hash(content)),
                    memory_type=mem_type,
                    tier=result_tier,
                    content=content,
                    confidence=result.get('confidence', 1.0) if isinstance(result, dict) else 1.0,
                    metadata={'raw_result': result}
                ))
            
            return memories[:limit]
        except Exception as e:
            print(f"⚠️  MCE 检索失败: {e}")
            return self._retrieve_local(query, tier, memory_type, limit)
    
    def _retrieve_local(self, query: str, tier: MemoryTier = None,
                       memory_type: MemoryType = None, limit: int = 10) -> List[MemoryItem]:
        results = []
        query_lower = query.lower()
        
        tiers_to_search = [tier] if tier else list(MemoryTier)
        
        for search_tier in tiers_to_search:
            for memory in self._local_memories.get(search_tier.value, []):
                if memory_type and memory.memory_type != memory_type:
                    continue
                
                if query_lower in memory.content.lower():
                    results.append(memory)
        
        results.sort(key=lambda x: x.confidence * x.weight, reverse=True)
        return results[:limit]
    
    def apply_forgetting(self, decay_factor: float = 0.9, min_weight: float = 0.1) -> int:
        forgotten_count = 0
        
        for tier_value, memories in self._local_memories.items():
            remaining = []
            for memory in memories:
                memory.weight *= decay_factor
                if memory.weight >= min_weight:
                    remaining.append(memory)
                else:
                    forgotten_count += 1
            self._local_memories[tier_value] = remaining
        
        return forgotten_count
    
    def get_statistics(self) -> Dict[str, Any]:
        stats = {
            'total_memories': 0,
            'by_tier': {},
            'by_type': {},
            'mce_enabled': self._use_mce
        }
        
        for tier, memories in self._local_memories.items():
            stats['by_tier'][tier] = len(memories)
            stats['total_memories'] += len(memories)
        
        for tier_memories in self._local_memories.values():
            for memory in tier_memories:
                type_name = memory.memory_type.value
                stats['by_type'][type_name] = stats['by_type'].get(type_name, 0) + 1
        
        return stats
    
    def to_knowledge_item(self, memory: MemoryItem) -> Dict[str, Any]:
        return {
            'id': memory.memory_id,
            'category': memory.memory_type.value,
            'title': memory.content[:50] + '...' if len(memory.content) > 50 else memory.content,
            'content': {'text': memory.content, 'metadata': memory.metadata},
            'tags': memory.tags,
            'source': memory.source,
            'confidence': memory.confidence,
            'usage_count': 0,
            'created_at': memory.created_at,
            'updated_at': memory.updated_at
        }
    
    def to_experience_item(self, memory: MemoryItem) -> Dict[str, Any]:
        return {
            'id': memory.memory_id,
            'task_id': memory.metadata.get('task_id', ''),
            'task_type': memory.memory_type.value,
            'success': memory.metadata.get('success', True),
            'description': memory.content,
            'lessons_learned': memory.metadata.get('lessons_learned', []),
            'patterns': memory.tags,
            'created_at': memory.created_at
        }


memory_adapter = MemoryAdapter()

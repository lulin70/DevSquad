#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户意图识别系统 v1.0

基于历史对话和语义理解，实现智能意图识别和需求分类。

核心功能:
1. 基于历史对话的意图识别
2. 用户需求类型自动分类
3. 常见问题模式识别
4. 意图驱动的对话流程
5. 自然语言触发机制
"""

import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 导入现有的语义匹配和角色调度功能
try:
    from ai_semantic_matcher import AISemanticMatcher
    from role_matcher import RoleMatcher, TaskRequirement, RoleDefinition, MatchStrategy
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("⚠️  语义匹配和角色调度模块不可用，将使用简化实现")


class IntentType(Enum):
    """意图类型"""
    CODE_ANALYSIS = "code_analysis"  # 代码分析
    DOCUMENTATION = "documentation"  # 文档处理
    ARCHITECTURE = "architecture"  # 架构设计
    FEATURE_REQUEST = "feature_request"  # 功能请求
    BUG_REPORT = "bug_report"  # Bug 报告
    QUESTION = "question"  # 问题咨询
    GENERAL = "general"  # 通用意图
    PROJECT_LIFECYCLE = "project_lifecycle"  # 项目全生命周期
    PLANNING = "planning"  # 规划
    KNOWLEDGE_MANAGEMENT = "knowledge_management"  # 知识管理
    UNKNOWN = "unknown"  # 未知意图


class NeedType(Enum):
    """需求类型"""
    NEW_FEATURE = "new_feature"  # 新功能
    IMPROVEMENT = "improvement"  # 改进
    BUG_FIX = "bug_fix"  # Bug 修复
    CONSULTATION = "consultation"  # 咨询
    DOCUMENTATION = "documentation"  # 文档
    TRAINING = "training"  # 培训
    OTHER = "other"  # 其他


@dataclass
class IntentRecognitionResult:
    """意图识别结果"""
    intent_type: IntentType
    intent_name: str
    confidence: float  # 置信度 (0-1)
    need_type: NeedType
    need_description: str
    key_phrases: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueContext:
    """对话上下文"""
    user_id: str
    session_id: str
    history: List[Dict[str, Any]]  # 对话历史
    current_message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternRecognitionResult:
    """模式识别结果"""
    pattern_id: str
    pattern_name: str
    confidence: float
    match_phrases: List[str]
    solution: Optional[str] = None


class UserIntentRecognizer:
    """
    用户意图识别器
    
    基于历史对话和语义理解，实现智能意图识别和需求分类。
    """

    def __init__(self):
        """
        初始化用户意图识别器
        """
        self.intent_patterns = self._load_intent_patterns()
        self.need_patterns = self._load_need_patterns()
        self.common_questions = self._load_common_questions()
        self.context_history: Dict[str, List[DialogueContext]] = {}
        
        # 初始化 AI 语义匹配器（如果可用）
        if AI_AVAILABLE:
            self.ai_matcher = AISemanticMatcher()
            print("✅ AI 语义匹配器已初始化")
        else:
            self.ai_matcher = None
            print("⚠️  AI 语义匹配器未初始化，使用规则匹配")

    def _load_intent_patterns(self) -> Dict[IntentType, List[str]]:
        return {
            IntentType.CODE_ANALYSIS: [
                r'分析代码', r'代码审查', r'代码质量', r'代码走读',
                r'code analysis', r'code review', r'code quality', r'code walkthrough'
            ],
            IntentType.DOCUMENTATION: [
                r'文档', r'编写文档', r'文档生成', r'文档验证',
                r'documentation', r'write doc', r'generate doc', r'doc validation'
            ],
            IntentType.ARCHITECTURE: [
                r'架构', r'设计架构', r'系统设计', r'技术选型',
                r'architecture', r'system design', r'technical selection'
            ],
            IntentType.FEATURE_REQUEST: [
                r'添加功能', r'新功能', r'功能请求', r'实现功能',
                r'add feature', r'new feature', r'feature request', r'implement feature'
            ],
            IntentType.BUG_REPORT: [
                r'bug', r'错误', r'问题', r'修复',
                r'bug report', r'error', r'issue', r'fix'
            ],
            IntentType.QUESTION: [
                r'如何', r'为什么', r'什么', r'怎样',
                r'how', r'why', r'what', r'how to'
            ],
            IntentType.GENERAL: [
                r'你好', r'问候', r'帮助', r'支持',
                r'hello', r'greeting', r'help', r'support'
            ],
            IntentType.PROJECT_LIFECYCLE: [
                r'项目生命周期', r'全生命周期', r'完整流程', r'标准流程',
                r'启动项目', r'新项目', r'从头开始', r'完整开发',
                r'需求分析.*架构.*开发', r'需求.*设计.*实现.*测试',
                r'project lifecycle', r'full lifecycle', r'complete flow',
                r'start project', r'new project', r'from scratch',
                r'完整功能', r'端到端', r'end.to.end', r'全流程'
            ],
            IntentType.PLANNING: [
                r'生成计划', r'项目计划', r'规划', r'制定计划',
                r'generate plan', r'project plan', r'planning'
            ],
            IntentType.KNOWLEDGE_MANAGEMENT: [
                r'提取知识', r'搜索知识', r'推荐知识', r'知识管理',
                r'extract knowledge', r'search knowledge', r'recommend knowledge'
            ]
        }

    def _load_need_patterns(self) -> Dict[NeedType, List[str]]:
        """
        加载需求模式
        
        Returns:
            Dict[NeedType, List[str]]: 需求类型到关键词模式的映射
        """
        return {
            NeedType.NEW_FEATURE: [
                r'新增', r'添加', r'新功能', r'实现',
                r'add', r'new', r'implement', r'create'
            ],
            NeedType.IMPROVEMENT: [
                r'优化', r'改进', r'提升', r'增强',
                r'optimize', r'improve', r'enhance', r'better'
            ],
            NeedType.BUG_FIX: [
                r'修复', r'bug', r'错误', r'问题',
                r'fix', r'bug', r'error', r'issue'
            ],
            NeedType.CONSULTATION: [
                r'咨询', r'建议', r'如何', r'指导',
                r'consult', r'advice', r'how', r'guide'
            ],
            NeedType.DOCUMENTATION: [
                r'文档', r'编写', r'生成', r'更新',
                r'document', r'write', r'generate', r'update'
            ],
            NeedType.TRAINING: [
                r'培训', r'学习', r'教程', r'指导',
                r'training', r'learn', r'tutorial', r'guide'
            ]
        }

    def _load_common_questions(self) -> List[Dict[str, Any]]:
        """
        加载常见问题
        
        Returns:
            List[Dict[str, Any]]: 常见问题列表
        """
        return [
            {
                "pattern_id": "faq_1",
                "pattern_name": "如何使用代码走读功能",
                "patterns": [
                    r'如何使用代码走读', r'代码走读功能', r'代码分析',
                    r'how to use code walkthrough', r'code walkthrough feature'
                ],
                "solution": "您可以使用 `python multi_role_code_walkthrough.py <project_root>` 命令来执行代码走读，系统会生成多角色分析报告和代码地图。"
            },
            {
                "pattern_id": "faq_2",
                "pattern_name": "如何检测代码质量",
                "patterns": [
                    r'代码质量', r'质量检测', r'代码问题',
                    r'code quality', r'quality check', r'code issues'
                ],
                "solution": "您可以使用交付物质量控制模块来检测代码质量，运行 `python deliverable_quality_control.py <project_root>` 命令。"
            },
            {
                "pattern_id": "faq_3",
                "pattern_name": "如何添加新功能",
                "patterns": [
                    r'添加新功能', r'实现功能', r'新功能开发',
                    r'add new feature', r'implement feature', r'new feature development'
                ],
                "solution": "您可以通过产品经理角色分析需求，然后由架构师设计架构，最后由开发工程师实现功能。"
            }
        ]

    def recognize_intent(self, context: DialogueContext) -> IntentRecognitionResult:
        """
        识别用户意图
        
        Args:
            context: 对话上下文
            
        Returns:
            IntentRecognitionResult: 意图识别结果
        """
        print(f"🧠 开始意图识别...")
        print(f"   用户消息: {context.current_message[:100]}...")

        # 提取关键短语
        key_phrases = self._extract_key_phrases(context.current_message)

        # 识别意图类型
        intent_type, intent_confidence = self._detect_intent_type(context)

        # 识别需求类型
        need_type, need_confidence = self._detect_need_type(context)

        # 生成建议
        recommendations = self._generate_recommendations(intent_type, need_type, context)

        # 构建结果
        result = IntentRecognitionResult(
            intent_type=intent_type,
            intent_name=intent_type.value,
            confidence=max(intent_confidence, need_confidence),
            need_type=need_type,
            need_description=need_type.value,
            key_phrases=key_phrases,
            recommendations=recommendations,
            metadata={
                "intent_confidence": intent_confidence,
                "need_confidence": need_confidence,
                "message_length": len(context.current_message)
            }
        )

        # 记录上下文
        self._record_context(context)

        return result

    def _detect_intent_type(self, context: DialogueContext) -> Tuple[IntentType, float]:
        """
        检测意图类型
        
        Args:
            context: 对话上下文
            
        Returns:
            Tuple[IntentType, float]: 意图类型和置信度
        """
        message = context.current_message.lower()
        scores = {}

        # 基于规则的意图检测
        for intent_type, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, message):
                    score += 1
            scores[intent_type] = min(score / len(patterns), 1.0)

        # 考虑对话历史
        if context.history:
            recent_history = context.history[-3:]  # 最近3条消息
            for history_item in recent_history:
                history_message = history_item.get('message', '').lower()
                for intent_type, patterns in self.intent_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, history_message):
                            scores[intent_type] = min(scores.get(intent_type, 0) + 0.2, 1.0)

        # 找出得分最高的意图
        if scores:
            best_intent = max(scores.items(), key=lambda x: x[1])
            return best_intent[0], best_intent[1]
        else:
            return IntentType.UNKNOWN, 0.0

    def _detect_need_type(self, context: DialogueContext) -> Tuple[NeedType, float]:
        """
        检测需求类型
        
        Args:
            context: 对话上下文
            
        Returns:
            Tuple[NeedType, float]: 需求类型和置信度
        """
        message = context.current_message.lower()
        scores = {}

        # 基于规则的需求检测
        for need_type, patterns in self.need_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, message):
                    score += 1
            scores[need_type] = min(score / len(patterns), 1.0)

        # 考虑对话历史
        if context.history:
            recent_history = context.history[-3:]
            for history_item in recent_history:
                history_message = history_item.get('message', '').lower()
                for need_type, patterns in self.need_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, history_message):
                            scores[need_type] = min(scores.get(need_type, 0) + 0.2, 1.0)

        # 找出得分最高的需求类型
        if scores:
            best_need = max(scores.items(), key=lambda x: x[1])
            return best_need[0], best_need[1]
        else:
            return NeedType.OTHER, 0.0

    def _extract_key_phrases(self, message: str) -> List[str]:
        """
        提取关键短语
        
        Args:
            message: 用户消息
            
        Returns:
            List[str]: 关键短语列表
        """
        # 简单的关键短语提取
        phrases = []
        
        # 提取技术术语
        tech_terms = ['代码', '文档', '架构', '功能', 'bug', '测试', '部署',
                     'code', 'document', 'architecture', 'feature', 'bug', 'test', 'deploy']
        for term in tech_terms:
            if term in message:
                phrases.append(term)
        
        # 提取动作词
        action_terms = ['分析', '设计', '实现', '修复', '优化', '创建', '更新',
                       'analyze', 'design', 'implement', 'fix', 'optimize', 'create', 'update']
        for term in action_terms:
            if term in message:
                phrases.append(term)
        
        return list(set(phrases))

    def _generate_recommendations(self, intent_type: IntentType, 
                                need_type: NeedType, 
                                context: DialogueContext) -> List[str]:
        recommendations = []

        if intent_type == IntentType.CODE_ANALYSIS:
            if need_type == NeedType.IMPROVEMENT:
                recommendations.append("您可以使用代码走读功能分析代码质量，然后根据报告进行优化")
            elif need_type == NeedType.BUG_FIX:
                recommendations.append("您可以使用代码分析功能定位问题，然后进行修复")
        elif intent_type == IntentType.DOCUMENTATION:
            recommendations.append("您可以使用文档验证功能检查文档质量")
        elif intent_type == IntentType.ARCHITECTURE:
            recommendations.append("您可以使用架构师角色进行系统设计和技术选型")
        elif intent_type == IntentType.FEATURE_REQUEST:
            recommendations.append("您可以通过产品经理角色分析需求，然后由开发工程师实现")
        elif intent_type == IntentType.PROJECT_LIFECYCLE:
            recommendations.append("建议使用项目全生命周期模式：需求分析→架构设计→UI设计→测试设计→任务分解→开发实现→测试验证→发布评审")
            recommendations.append("使用命令 /mas lifecycle <任务> 启动完整项目流程")
        elif intent_type == IntentType.PLANNING:
            recommendations.append("使用命令 /mas plan <项目信息> 生成项目计划")
        elif intent_type == IntentType.KNOWLEDGE_MANAGEMENT:
            recommendations.append("使用命令 /mas extract/search/recommend 进行知识管理")
        elif intent_type == IntentType.QUESTION:
            pattern_result = self.recognize_pattern(context.current_message)
            if pattern_result and pattern_result.solution:
                recommendations.append(pattern_result.solution)
            else:
                recommendations.append("请问您需要哪方面的帮助？")

        return recommendations

    def recognize_pattern(self, message: str) -> Optional[PatternRecognitionResult]:
        """
        识别常见问题模式
        
        Args:
            message: 用户消息
            
        Returns:
            Optional[PatternRecognitionResult]: 模式识别结果
        """
        message_lower = message.lower()
        best_match = None
        best_score = 0

        for faq in self.common_questions:
            score = 0
            match_phrases = []
            
            for pattern in faq.get('patterns', []):
                if re.search(pattern, message_lower):
                    score += 1
                    match_phrases.append(pattern)
            
            if score > best_score:
                best_score = score
                best_match = PatternRecognitionResult(
                    pattern_id=faq.get('pattern_id'),
                    pattern_name=faq.get('pattern_name'),
                    confidence=min(score / len(faq.get('patterns', 1)), 1.0),
                    match_phrases=match_phrases,
                    solution=faq.get('solution')
                )

        return best_match if best_match and best_match.confidence > 0.3 else None

    def suggest_dialogue_flow(self, intent_result: IntentRecognitionResult) -> List[str]:
        flow = []

        if intent_result.intent_type == IntentType.CODE_ANALYSIS:
            flow.extend([
                "确认分析范围",
                "执行代码分析",
                "生成分析报告",
                "提供改进建议"
            ])
        elif intent_result.intent_type == IntentType.DOCUMENTATION:
            flow.extend([
                "确认文档类型",
                "执行文档验证",
                "生成验证报告",
                "提供文档改进建议"
            ])
        elif intent_result.intent_type == IntentType.ARCHITECTURE:
            flow.extend([
                "收集需求信息",
                "执行架构设计",
                "生成架构文档",
                "进行架构评审"
            ])
        elif intent_result.intent_type == IntentType.FEATURE_REQUEST:
            flow.extend([
                "分析需求细节",
                "制定实现计划",
                "执行功能开发",
                "进行功能测试"
            ])
        elif intent_result.intent_type == IntentType.PROJECT_LIFECYCLE:
            flow.extend([
                "阶段1: 需求分析（产品经理）",
                "阶段2: 架构设计（架构师）",
                "阶段3: UI 设计（UI 设计师）",
                "阶段4: 测试设计（测试专家）",
                "阶段5: 任务分解（独立开发者）",
                "阶段6: 开发实现（独立开发者）",
                "阶段7: 测试验证（测试专家）",
                "阶段8: 发布评审（多角色）"
            ])
        elif intent_result.intent_type == IntentType.PLANNING:
            flow.extend([
                "收集项目信息",
                "分析项目需求",
                "生成项目计划",
                "分解任务清单"
            ])
        elif intent_result.intent_type == IntentType.KNOWLEDGE_MANAGEMENT:
            flow.extend([
                "识别知识类型",
                "执行知识操作",
                "更新知识库",
                "提供知识推荐"
            ])
        elif intent_result.intent_type == IntentType.QUESTION:
            flow.extend([
                "理解问题详情",
                "提供解决方案",
                "确认问题解决"
            ])

        return flow

    def _record_context(self, context: DialogueContext):
        """
        记录对话上下文
        
        Args:
            context: 对话上下文
        """
        user_id = context.user_id
        if user_id not in self.context_history:
            self.context_history[user_id] = []
        
        # 保留最近10条上下文
        self.context_history[user_id].append(context)
        if len(self.context_history[user_id]) > 10:
            self.context_history[user_id] = self.context_history[user_id][-10:]

    def get_user_history(self, user_id: str, limit: int = 5) -> List[DialogueContext]:
        """
        获取用户历史上下文
        
        Args:
            user_id: 用户 ID
            limit: 返回数量限制
            
        Returns:
            List[DialogueContext]: 历史上下文列表
        """
        if user_id in self.context_history:
            return self.context_history[user_id][-limit:]
        return []

    def handle_natural_language(self, message: str, user_id: str = "default") -> Dict[str, Any]:
        """
        处理自然语言指令
        
        Args:
            message: 用户消息
            user_id: 用户 ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 构建对话上下文
        context = DialogueContext(
            user_id=user_id,
            session_id=f"session_{datetime.now().timestamp()}",
            history=self.get_user_history(user_id),
            current_message=message,
            timestamp=datetime.now()
        )

        # 识别意图
        intent_result = self.recognize_intent(context)

        # 识别模式
        pattern_result = self.recognize_pattern(message)

        # 建议对话流程
        dialogue_flow = self.suggest_dialogue_flow(intent_result)

        return {
            "intent": {
                "type": intent_result.intent_type.value,
                "confidence": intent_result.confidence,
                "need_type": intent_result.need_type.value
            },
            "key_phrases": intent_result.key_phrases,
            "recommendations": intent_result.recommendations,
            "pattern": pattern_result.__dict__ if pattern_result else None,
            "dialogue_flow": dialogue_flow,
            "timestamp": datetime.now().isoformat()
        }


def main():
    """示例用法"""
    # 创建意图识别器
    recognizer = UserIntentRecognizer()

    # 测试消息
    test_messages = [
        "如何使用代码走读功能分析我的项目？",
        "我需要为我的项目添加一个新功能，如何实现？",
        "我的代码有质量问题，如何检测和修复？",
        "我想设计一个微服务架构，需要什么工具？"
    ]

    print("=" * 80)
    print("用户意图识别测试")
    print("=" * 80)

    for i, message in enumerate(test_messages):
        print(f"\n{ i+1 }. 用户消息: {message}")
        print("-" * 80)

        # 处理消息
        result = recognizer.handle_natural_language(message, f"user_{i}")

        # 打印结果
        print(f"✅ 意图类型: {result['intent']['type']}")
        print(f"   置信度: {result['intent']['confidence']:.2%}")
        print(f"   需求类型: {result['intent']['need_type']}")
        print(f"   关键短语: {', '.join(result['key_phrases'])}")
        
        if result['recommendations']:
            print(f"   建议: {result['recommendations'][0]}")
        
        if result['pattern']:
            print(f"   匹配模式: {result['pattern']['pattern_name']}")
        
        print(f"   对话流程:")
        for j, step in enumerate(result['dialogue_flow'], 1):
            print(f"     {j}. {step}")

    # 测试对话历史影响
    print("\n" + "=" * 80)
    print("对话历史影响测试")
    print("=" * 80)

    # 模拟多轮对话
    user_id = "test_user"
    messages = [
        "我需要分析代码质量",
        "具体如何操作？",
        "分析结果如何查看？"
    ]

    for message in messages:
        print(f"\n用户消息: {message}")
        result = recognizer.handle_natural_language(message, user_id)
        print(f"✅ 意图类型: {result['intent']['type']}")
        print(f"   置信度: {result['intent']['confidence']:.2%}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心规则库

整合了Claude Code的14条提示词核心规则和MultiAgentSkill的现有规则
提供统一的规则管理和应用接口
"""

from typing import List, Dict, Optional

class CoreRules:
    """核心规则管理类"""
    
    def __init__(self):
        self.rules = self._load_rules()
    
    def _load_rules(self) -> List[Dict]:
        """加载核心规则"""
        return [
            {
                "id": "rule_1",
                "name": "用禁令代替指令",
                "description": "多用\"绝不\"\"不准\"设定边界，明确禁止的行为",
                "examples": [
                    "绝不使用占位符代码",
                    "不准简化需求",
                    "禁止硬编码敏感信息"
                ],
                "application": "在所有角色Prompt中明确禁止行为"
            },
            {
                "id": "rule_2",
                "name": "设置唱反调角色",
                "description": "专找问题而非确认可行，在多角色协作中添加批判性审查",
                "examples": [
                    "作为批判性审查者，找出方案中的问题",
                    "检查设计中的潜在风险",
                    "识别实现中的缺陷"
                ],
                "application": "在多角色协作中添加'批判性审查者'角色"
            },
            {
                "id": "rule_3",
                "name": "建立反驳话术库",
                "description": "应对\"看起来没问题\"等借口，提供标准化的反驳话术",
                "examples": [
                    "这个方案在边界情况下可能会失败",
                    "我们需要考虑性能影响",
                    "安全性方面还有改进空间"
                ],
                "application": "为智能体提供标准化的反驳话术"
            },
            {
                "id": "rule_4",
                "name": "避免画蛇添足",
                "description": "不添加未要求内容，接受适度重复",
                "examples": [
                    "只实现要求的功能",
                    "不添加额外的特性",
                    "保持代码简洁"
                ],
                "application": "在所有角色Prompt中强调'只做要求的事情'"
            },
            {
                "id": "rule_5",
                "name": "如实汇报原则",
                "description": "不润色也不过度谦虚，客观汇报进度和问题",
                "examples": [
                    "任务已完成80%，遇到了X问题",
                    "这个功能实现存在性能瓶颈",
                    "需要额外的时间来完成测试"
                ],
                "application": "要求智能体客观汇报进度和问题"
            },
            {
                "id": "rule_6",
                "name": "保留核心思考",
                "description": "活可分出去，但理解不能外包，确保对任务的核心理解",
                "examples": [
                    "先理解需求再执行",
                    "保留对核心问题的分析",
                    "确保理解任务的本质"
                ],
                "application": "确保智能体在协作中保留对任务的核心理解"
            },
            {
                "id": "rule_7",
                "name": "诚实面对未知",
                "description": "不知道就说不知道，不猜测或编造信息",
                "examples": [
                    "关于这个问题，我需要更多信息",
                    "我无法确定，需要进一步研究",
                    "这个领域超出了我的知识范围"
                ],
                "application": "鼓励智能体在遇到不确定时明确表示"
            },
            {
                "id": "rule_8",
                "name": "先看再改",
                "description": "编辑前必须确认内容，理解现有代码或文档",
                "examples": [
                    "先阅读完整的代码再修改",
                    "理解现有架构后再设计",
                    "分析现有文档后再更新"
                ],
                "application": "要求智能体在修改代码或文档前先完整阅读"
            },
            {
                "id": "rule_9",
                "name": "授权有时效",
                "description": "一次授权≠永久许可，明确决策权限范围和时效",
                "examples": [
                    "在X范围内可以自主决策",
                    "超过预算需要重新审批",
                    "技术选型需要架构师确认"
                ],
                "application": "明确智能体的决策权限范围和时效"
            },
            {
                "id": "rule_10",
                "name": "解释规则原因",
                "description": "让AI理解\"为什么\"，增强规则的执行效果",
                "examples": [
                    "这样做是为了提高代码可维护性",
                    "这个规则有助于保证系统安全",
                    "遵循这个规范可以提升用户体验"
                ],
                "application": "在Prompt中解释规则背后的原因"
            },
            {
                "id": "rule_11",
                "name": "按需提供信息",
                "description": "用到再给，避免过载，采用渐进式信息提供",
                "examples": [
                    "先提供核心需求，细节稍后补充",
                    "根据进展逐步提供更多信息",
                    "只提供与当前任务相关的信息"
                ],
                "application": "采用渐进式信息提供，避免信息过载"
            },
            {
                "id": "rule_12",
                "name": "沟通规范到标点",
                "description": "禁用表情，语言精炼，统一沟通风格和格式",
                "examples": [
                    "使用简洁专业的语言",
                    "避免使用表情符号",
                    "保持格式一致"
                ],
                "application": "统一智能体的沟通风格和格式"
            },
            {
                "id": "rule_13",
                "name": "优化表达顺序",
                "description": "先铺垫后要求，调整Prompt结构",
                "examples": [
                    "先介绍背景，再提出要求",
                    "先说明目标，再描述步骤",
                    "先提供上下文，再给出具体任务"
                ],
                "application": "调整Prompt结构，先铺垫背景再提出要求"
            },
            {
                "id": "rule_14",
                "name": "模块化设计",
                "description": "按场景组合独立功能模块，提高可维护性",
                "examples": [
                    "将Prompt按功能模块组织",
                    "使用模块化的代码结构",
                    "按场景组合独立功能"
                ],
                "application": "将Prompt和功能按场景模块化"
            },
            {
                "id": "rule_15",
                "name": "系统性思维规则",
                "description": "确保设计完整性，设计前回答4个关键问题",
                "examples": [
                    "系统的边界是什么？",
                    "核心功能是什么？",
                    "如何验证系统的正确性？",
                    "未来如何扩展？"
                ],
                "application": "在架构设计和系统规划中应用"
            },
            {
                "id": "rule_16",
                "name": "深度思考规则",
                "description": "5-Why分析法找根因，连续追问找到问题本质",
                "examples": [
                    "为什么会出现这个问题？",
                    "为什么这个解决方案可行？",
                    "为什么需要这个功能？"
                ],
                "application": "在问题分析和解决方案设计中应用"
            },
            {
                "id": "rule_17",
                "name": "零容忍清单",
                "description": "明确禁止的行为，如mock、硬编码、简化",
                "examples": [
                    "禁止使用占位符代码",
                    "禁止硬编码敏感信息",
                    "禁止简化需求"
                ],
                "application": "在所有角色Prompt中明确禁止行为"
            },
            {
                "id": "rule_18",
                "name": "验证驱动设计",
                "description": "完整验收标准，确保功能可验证",
                "examples": [
                    "定义明确的验收标准",
                    "设计可测试的接口",
                    "确保功能可验证"
                ],
                "application": "在需求分析和设计阶段应用"
            },
            {
                "id": "rule_19",
                "name": "完整性检查",
                "description": "多维度检查清单，确保任务完成质量",
                "examples": [
                    "代码质量检查",
                    "安全性检查",
                    "性能检查",
                    "可维护性检查"
                ],
                "application": "在任务完成前进行多维度检查"
            },
            {
                "id": "rule_20",
                "name": "自测规则",
                "description": "3层测试验证，确保代码质量",
                "examples": [
                    "单元测试",
                    "集成测试",
                    "端到端测试"
                ],
                "application": "在开发实现阶段应用"
            }
        ]
    
    def get_rule_by_id(self, rule_id: str) -> Optional[Dict]:
        """根据ID获取规则"""
        for rule in self.rules:
            if rule["id"] == rule_id:
                return rule
        return None
    
    def get_rules_by_category(self, category: str) -> List[Dict]:
        """根据类别获取规则"""
        # 这里可以根据需要实现分类逻辑
        return self.rules
    
    def get_all_rules(self) -> List[Dict]:
        """获取所有规则"""
        return self.rules
    
    def apply_rules_to_prompt(self, prompt: str, role: str) -> str:
        """将规则应用到Prompt中"""
        # 根据角色选择适用的规则
        applicable_rules = self._get_applicable_rules(role)
        
        # 构建规则提示
        rules_prompt = "\n\n## 核心规则\n"
        rules_prompt += "请严格遵循以下核心规则：\n"
        
        for rule in applicable_rules:
            rules_prompt += f"- **{rule['name']}**: {rule['description']}\n"
            if rule['examples']:
                rules_prompt += "  示例：" + ", ".join(rule['examples'][:3]) + "\n"
        
        return prompt + rules_prompt
    
    def _get_applicable_rules(self, role: str) -> List[Dict]:
        """根据角色获取适用的规则"""
        # 所有角色都适用的规则
        all_rules = [
            "rule_1", "rule_4", "rule_5", "rule_6", "rule_7", 
            "rule_8", "rule_10", "rule_11", "rule_12", "rule_13"
        ]
        
        # 角色特定规则
        role_specific_rules = {
            "architect": ["rule_2", "rule_15", "rule_16", "rule_19"],
            "product-manager": ["rule_2", "rule_10", "rule_18"],
            "tester": ["rule_2", "rule_19", "rule_20"],
            "solo-coder": ["rule_3", "rule_17", "rule_20"],
            "ui-designer": ["rule_4", "rule_14"]
        }
        
        # 构建适用规则列表
        applicable_rule_ids = all_rules.copy()
        if role in role_specific_rules:
            applicable_rule_ids.extend(role_specific_rules[role])
        
        # 去重并返回规则
        unique_rule_ids = list(set(applicable_rule_ids))
        return [rule for rule in self.rules if rule["id"] in unique_rule_ids]

# 全局规则实例
core_rules = CoreRules()

if __name__ == "__main__":
    # 测试规则加载
    rules = core_rules.get_all_rules()
    print(f"加载了 {len(rules)} 条核心规则")
    
    # 测试规则应用
    test_prompt = "你是一名架构师，负责设计系统架构"
    enhanced_prompt = core_rules.apply_rules_to_prompt(test_prompt, "architect")
    print("\n增强后的Prompt:")
    print(enhanced_prompt)
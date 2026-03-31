#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding 提示词自我进化系统

实现提示词生成和优化系统，包括 Alpha（生成器）和 Omega（优化器）提示。
"""

import os
import json
import time
from datetime import datetime

class PromptEvolutionSystem:
    """提示词自我进化系统类，负责生成和优化提示词"""
    
    def __init__(self, memory_bank_path=None):
        """
        初始化提示词进化系统
        
        Args:
            memory_bank_path (str): 记忆库路径
        """
        self.memory_bank_path = memory_bank_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'memory-bank'
        )
        self.prompts_dir = os.path.join(self.memory_bank_path, 'prompts')
        self.evolution_dir = os.path.join(self.memory_bank_path, 'prompt_evolution')
        os.makedirs(self.prompts_dir, exist_ok=True)
        os.makedirs(self.evolution_dir, exist_ok=True)
        
        # 初始化默认提示词模板
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """
        初始化默认提示词模板
        """
        default_templates = {
            'alpha_generator': {
                'name': 'Alpha 生成器提示',
                'description': '用于生成新的提示词',
                'template': '''你是一个提示词生成专家，负责为特定任务生成高质量的提示词。\n\n任务描述：{task_description}\n\n请生成一个详细、具体、有效的提示词，包含以下要素：\n1. 明确的角色定位\n2. 详细的任务描述\n3. 具体的输出要求\n4. 相关的约束条件\n5. 示例（如有必要）\n\n生成的提示词应该：\n- 清晰明确，避免歧义\n- 具体详细，提供足够的上下文\n- 针对性强，与任务高度相关\n- 格式规范，易于理解和使用\n\n请输出完整的提示词：''',
                'created_at': datetime.now().isoformat()
            },
            'omega_optimizer': {
                'name': 'Omega 优化器提示',
                'description': '用于优化现有提示词',
                'template': '''你是一个提示词优化专家，负责改进和优化现有的提示词。\n\n原始提示词：\n{original_prompt}\n\n优化要求：\n1. 分析原始提示词的优缺点\n2. 保留有效的部分\n3. 改进模糊或不明确的部分\n4. 增强提示词的针对性和有效性\n5. 确保提示词清晰、具体、可执行\n\n优化后的提示词应该：\n- 更清晰明确\n- 更具体详细\n- 更有针对性\n- 更易于理解和使用\n- 能够产生更好的结果\n\n请输出优化后的提示词：''',
                'created_at': datetime.now().isoformat()
            }
        }
        
        # 保存默认模板
        for template_name, template_data in default_templates.items():
            template_file = os.path.join(self.prompts_dir, f"{template_name}.json")
            if not os.path.exists(template_file):
                with open(template_file, 'w', encoding='utf-8') as f:
                    json.dump(template_data, f, ensure_ascii=False, indent=2)
    
    def generate_prompt(self, task_description, template_name='alpha_generator'):
        """
        生成提示词
        
        Args:
            task_description (str): 任务描述
            template_name (str): 模板名称
        
        Returns:
            str: 生成的提示词
        """
        # 加载模板
        template_file = os.path.join(self.prompts_dir, f"{template_name}.json")
        if not os.path.exists(template_file):
            raise FileNotFoundError(f"模板文件不存在: {template_file}")
        
        with open(template_file, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        
        # 生成提示词
        prompt = template_data['template'].format(
            task_description=task_description
        )
        
        # 保存生成的提示词
        self._save_generated_prompt(task_description, prompt, 'generated')
        
        return prompt
    
    def optimize_prompt(self, original_prompt, template_name='omega_optimizer'):
        """
        优化提示词
        
        Args:
            original_prompt (str): 原始提示词
            template_name (str): 模板名称
        
        Returns:
            str: 优化后的提示词
        """
        # 加载模板
        template_file = os.path.join(self.prompts_dir, f"{template_name}.json")
        if not os.path.exists(template_file):
            raise FileNotFoundError(f"模板文件不存在: {template_file}")
        
        with open(template_file, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        
        # 生成优化提示词
        optimization_prompt = template_data['template'].format(
            original_prompt=original_prompt
        )
        
        # 保存优化过程
        self._save_generated_prompt(original_prompt, optimization_prompt, 'optimized')
        
        return optimization_prompt
    
    def _save_generated_prompt(self, input_text, output_prompt, prompt_type):
        """
        保存生成的提示词
        
        Args:
            input_text (str): 输入文本
            output_prompt (str): 输出提示词
            prompt_type (str): 提示词类型
        """
        prompt_data = {
            'id': f"prompt_{int(time.time())}",
            'created_at': datetime.now().isoformat(),
            'type': prompt_type,
            'input': input_text,
            'output': output_prompt
        }
        
        # 保存到进化目录
        prompt_file = os.path.join(self.evolution_dir, f"{prompt_data['id']}.json")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, ensure_ascii=False, indent=2)
    
    def get_prompt_history(self, limit=10):
        """
        获取提示词历史
        
        Args:
            limit (int): 返回的历史数量限制
        
        Returns:
            list: 提示词历史列表
        """
        history = []
        
        if not os.path.exists(self.evolution_dir):
            return history
        
        # 读取所有提示词文件
        for filename in os.listdir(self.evolution_dir):
            if filename.endswith('.json'):
                prompt_file = os.path.join(self.evolution_dir, filename)
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    try:
                        prompt_data = json.load(f)
                        # 处理分析文件的情况
                        if 'prompt_id' in prompt_data:
                            prompt_data['id'] = prompt_data['prompt_id']
                            prompt_data['type'] = 'analysis'
                        history.append(prompt_data)
                    except json.JSONDecodeError:
                        pass
        
        # 按创建时间排序
        history.sort(key=lambda x: x['created_at'], reverse=True)
        
        # 返回限制数量
        return history[:limit]
    
    def analyze_prompt_effectiveness(self, prompt, feedback):
        """
        分析提示词效果
        
        Args:
            prompt (str): 提示词
            feedback (str): 反馈信息
        
        Returns:
            dict: 分析结果
        """
        # 简单的效果分析
        analysis = {
            'prompt_id': f"analysis_{int(time.time())}",
            'created_at': datetime.now().isoformat(),
            'prompt': prompt,
            'feedback': feedback,
            'effectiveness_score': self._calculate_effectiveness_score(feedback),
            'suggestions': self._generate_improvement_suggestions(prompt, feedback)
        }
        
        # 保存分析结果
        analysis_file = os.path.join(self.evolution_dir, f"{analysis['prompt_id']}.json")
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        return analysis
    
    def _calculate_effectiveness_score(self, feedback):
        """
        计算提示词效果分数
        
        Args:
            feedback (str): 反馈信息
        
        Returns:
            int: 效果分数 (0-100)
        """
        # 简单的分数计算逻辑
        positive_keywords = ['好', '优秀', '有效', '满意', '成功', '准确', '清晰']
        negative_keywords = ['差', '无效', '不满意', '失败', '错误', '模糊']
        
        score = 50  # 基础分数
        
        # 增加正面关键词分数
        for keyword in positive_keywords:
            if keyword in feedback:
                score += 10
        
        # 减少负面关键词分数
        for keyword in negative_keywords:
            if keyword in feedback:
                score -= 10
        
        # 确保分数在 0-100 之间
        return max(0, min(100, score))
    
    def _generate_improvement_suggestions(self, prompt, feedback):
        """
        生成改进建议
        
        Args:
            prompt (str): 提示词
            feedback (str): 反馈信息
        
        Returns:
            list: 改进建议列表
        """
        suggestions = []
        
        # 基于反馈生成建议
        if '模糊' in feedback or '不明确' in feedback:
            suggestions.append('增加具体细节，使任务要求更明确')
        
        if '复杂' in feedback or '难以理解' in feedback:
            suggestions.append('简化语言，提高提示词的可读性')
        
        if '无效' in feedback or '效果不好' in feedback:
            suggestions.append('调整提示词结构，增强针对性')
        
        if '缺少' in feedback:
            suggestions.append('补充缺失的信息和要求')
        
        if not suggestions:
            suggestions.append('提示词效果良好，继续保持')
        
        return suggestions
    
    def create_custom_template(self, template_name, template_data):
        """
        创建自定义模板
        
        Args:
            template_name (str): 模板名称
            template_data (dict): 模板数据
        """
        # 验证模板数据
        required_fields = ['name', 'description', 'template']
        for field in required_fields:
            if field not in template_data:
                raise ValueError(f"模板数据缺少必需字段: {field}")
        
        # 添加创建时间
        template_data['created_at'] = datetime.now().isoformat()
        
        # 保存模板
        template_file = os.path.join(self.prompts_dir, f"{template_name}.json")
        with open(template_file, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
    
    def list_templates(self):
        """
        列出所有模板
        
        Returns:
            list: 模板列表
        """
        templates = []
        
        if not os.path.exists(self.prompts_dir):
            return templates
        
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith('.json'):
                template_file = os.path.join(self.prompts_dir, filename)
                with open(template_file, 'r', encoding='utf-8') as f:
                    try:
                        template_data = json.load(f)
                        template_data['id'] = filename[:-5]  # 移除 .json 后缀
                        templates.append(template_data)
                    except json.JSONDecodeError:
                        pass
        
        return templates

if __name__ == '__main__':
    # 测试提示词进化系统
    system = PromptEvolutionSystem()
    
    # 测试生成提示词
    task_description = "创建一个React组件，显示用户列表，包含姓名、邮箱和电话"
    generated_prompt = system.generate_prompt(task_description)
    print("生成的提示词:")
    print(generated_prompt)
    print("\n" + "-" * 80 + "\n")
    
    # 测试优化提示词
    optimized_prompt = system.optimize_prompt(generated_prompt)
    print("优化后的提示词:")
    print(optimized_prompt)
    print("\n" + "-" * 80 + "\n")
    
    # 测试分析提示词效果
    feedback = "提示词非常清晰，生成的代码质量很高，但是可以增加一些样式要求"
    analysis = system.analyze_prompt_effectiveness(optimized_prompt, feedback)
    print("提示词效果分析:")
    print(f"效果分数: {analysis['effectiveness_score']}")
    print("改进建议:")
    for suggestion in analysis['suggestions']:
        print(f"- {suggestion}")
    print("\n" + "-" * 80 + "\n")
    
    # 测试列出模板
    templates = system.list_templates()
    print("可用模板:")
    for template in templates:
        print(f"- {template['id']}: {template['name']}")
    
    # 测试获取历史
    history = system.get_prompt_history(5)
    print("\n最近的提示词历史:")
    for item in history:
        print(f"- {item['id']} ({item['type']}): {item['created_at']}")

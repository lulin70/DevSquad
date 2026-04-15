#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户体验管理器

用于收集、分析用户反馈，优化界面交互流程，提升用户体验。
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path

class UserExperienceManager:
    """用户体验管理器类"""
    
    def __init__(self, data_path=None):
        """
        初始化用户体验管理器
        
        Args:
            data_path (str): 数据存储路径
        """
        self.data_path = data_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'memory-bank',
            'user_experience'
        )
        self.feedback_dir = os.path.join(self.data_path, 'feedback')
        self.interface_dir = os.path.join(self.data_path, 'interface')
        self.stats_path = os.path.join(self.data_path, 'stats.json')
        os.makedirs(self.feedback_dir, exist_ok=True)
        os.makedirs(self.interface_dir, exist_ok=True)
        self._init_stats()
    
    def _init_stats(self):
        """初始化统计数据"""
        if not os.path.exists(self.stats_path):
            stats = {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'feedback_count': 0,
                'feedback_categories': {},
                'interface_improvements': 0,
                'user_satisfaction': 0.0
            }
            self._save_stats(stats)
    
    def _load_stats(self):
        """加载统计数据"""
        with open(self.stats_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_stats(self, stats):
        """保存统计数据"""
        stats['last_updated'] = datetime.now().isoformat()
        with open(self.stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    
    def collect_feedback(self, user_id, feedback_type, content, rating=None, context=None):
        """
        收集用户反馈
        
        Args:
            user_id (str): 用户ID
            feedback_type (str): 反馈类型 (bug, feature, suggestion, question, praise)
            content (str): 反馈内容
            rating (int): 评分 (1-5)
            context (dict): 上下文信息
        
        Returns:
            str: 反馈ID
        """
        # 生成反馈ID
        feedback_id = f"feedback_{int(time.time())}"
        
        # 创建反馈文件
        feedback_file = os.path.join(self.feedback_dir, f"{feedback_id}.json")
        feedback = {
            'id': feedback_id,
            'user_id': user_id,
            'type': feedback_type,
            'content': content,
            'rating': rating,
            'context': context or {},
            'created_at': datetime.now().isoformat(),
            'status': 'pending',
            'analysis': {}
        }
        
        with open(feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback, f, ensure_ascii=False, indent=2)
        
        # 更新统计数据
        stats = self._load_stats()
        stats['feedback_count'] += 1
        if feedback_type not in stats['feedback_categories']:
            stats['feedback_categories'][feedback_type] = 0
        stats['feedback_categories'][feedback_type] += 1
        if rating:
            # 简单的满意度计算
            stats['user_satisfaction'] = (
                (stats['user_satisfaction'] * (stats['feedback_count'] - 1) + rating) / 
                stats['feedback_count']
            )
        self._save_stats(stats)
        
        # 分析反馈
        self.analyze_feedback(feedback_id)
        
        return feedback_id
    
    def analyze_feedback(self, feedback_id):
        """
        分析用户反馈
        
        Args:
            feedback_id (str): 反馈ID
        
        Returns:
            dict: 分析结果
        """
        # 加载反馈
        feedback_file = os.path.join(self.feedback_dir, f"{feedback_id}.json")
        if not os.path.exists(feedback_file):
            return None
        
        with open(feedback_file, 'r', encoding='utf-8') as f:
            feedback = json.load(f)
        
        # 基于规则的反馈分析
        analysis = {
            'category': self._categorize_feedback(feedback),
            'sentiment': self._analyze_sentiment(feedback),
            'priority': self._calculate_priority(feedback),
            'suggestions': self._generate_suggestions(feedback)
        }
        
        # 更新反馈文件
        feedback['analysis'] = analysis
        feedback['status'] = 'analyzed'
        
        with open(feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback, f, ensure_ascii=False, indent=2)
        
        return analysis
    
    def _categorize_feedback(self, feedback):
        """对反馈进行分类"""
        content = feedback['content'].lower()
        feedback_type = feedback['type']
        
        if feedback_type == 'bug':
            if 'crash' in content or 'error' in content or 'fail' in content:
                return 'critical_bug'
            elif 'slow' in content or 'lag' in content:
                return 'performance_issue'
            else:
                return 'general_bug'
        elif feedback_type == 'feature':
            if 'new' in content or 'add' in content:
                return 'new_feature'
            elif 'improve' in content or 'enhance' in content:
                return 'feature_improvement'
            else:
                return 'general_feature'
        elif feedback_type == 'suggestion':
            if 'ui' in content or 'interface' in content:
                return 'ui_suggestion'
            elif 'workflow' in content or 'process' in content:
                return 'workflow_suggestion'
            else:
                return 'general_suggestion'
        elif feedback_type == 'question':
            if 'how' in content or 'help' in content:
                return 'usage_question'
            elif 'why' in content or 'reason' in content:
                return 'technical_question'
            else:
                return 'general_question'
        elif feedback_type == 'praise':
            return 'general_praise'
        else:
            return 'unknown'
    
    def _analyze_sentiment(self, feedback):
        """分析反馈情感"""
        content = feedback['content'].lower()
        rating = feedback.get('rating', 3)
        
        positive_words = ['good', 'great', 'excellent', 'amazing', 'awesome', 'perfect', 'love', 'like', 'helpful', 'fast']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'slow', 'buggy', 'frustrating', 'difficult', 'confusing', 'disappointed']
        
        positive_count = sum(1 for word in positive_words if word in content)
        negative_count = sum(1 for word in negative_words if word in content)
        
        # 处理rating为None的情况
        if rating is not None:
            if rating >= 4 or positive_count > negative_count:
                return 'positive'
            elif rating <= 2 or negative_count > positive_count:
                return 'negative'
            else:
                return 'neutral'
        else:
            # 当没有评分时，仅基于文本情感
            if positive_count > negative_count:
                return 'positive'
            elif negative_count > positive_count:
                return 'negative'
            else:
                return 'neutral'
    
    def _calculate_priority(self, feedback):
        """计算反馈优先级"""
        feedback_type = feedback['type']
        rating = feedback.get('rating', 3)
        content = feedback['content'].lower()
        
        if feedback_type == 'bug':
            if 'crash' in content or 'error' in content:
                return 'high'
            elif 'slow' in content or 'lag' in content:
                return 'medium'
            else:
                return 'low'
        elif feedback_type == 'feature':
            if 'urgent' in content or 'need' in content:
                return 'high'
            else:
                return 'medium'
        elif feedback_type == 'suggestion':
            return 'low'
        elif feedback_type == 'question':
            if 'urgent' in content or 'immediate' in content:
                return 'high'
            else:
                return 'medium'
        else:  # praise
            return 'low'
    
    def _generate_suggestions(self, feedback):
        """生成改进建议"""
        feedback_type = feedback['type']
        category = self._categorize_feedback(feedback)
        suggestions = []
        
        if feedback_type == 'bug':
            if category == 'critical_bug':
                suggestions.append('立即修复此问题，确保系统稳定性')
                suggestions.append('添加更多的错误处理和异常捕获')
            elif category == 'performance_issue':
                suggestions.append('优化相关代码，提高系统性能')
                suggestions.append('添加性能监控，及时发现性能问题')
            else:
                suggestions.append('修复此bug并添加相应的测试用例')
        elif feedback_type == 'feature':
            if category == 'new_feature':
                suggestions.append('评估此功能的可行性和优先级')
                suggestions.append('设计详细的功能规范和实现计划')
            else:
                suggestions.append('分析现有功能的改进空间')
                suggestions.append('制定功能改进计划并实施')
        elif feedback_type == 'suggestion':
            if category == 'ui_suggestion':
                suggestions.append('审查UI设计，考虑用户的建议')
                suggestions.append('进行用户测试，验证改进效果')
            elif category == 'workflow_suggestion':
                suggestions.append('分析当前工作流程，找出优化空间')
                suggestions.append('重新设计工作流程，提高效率')
            else:
                suggestions.append('评估建议的可行性和价值')
                suggestions.append('考虑将建议纳入产品规划')
        elif feedback_type == 'question':
            suggestions.append('提供详细的解答和使用指导')
            suggestions.append('考虑在文档中添加相关内容，避免类似问题')
        
        return suggestions
    
    def get_feedback(self, feedback_id):
        """
        获取反馈详情
        
        Args:
            feedback_id (str): 反馈ID
        
        Returns:
            dict: 反馈详情
        """
        feedback_file = os.path.join(self.feedback_dir, f"{feedback_id}.json")
        if not os.path.exists(feedback_file):
            return None
        
        with open(feedback_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_feedback(self, filter_type=None):
        """
        列出反馈
        
        Args:
            filter_type (str): 过滤类型
        
        Returns:
            list: 反馈列表
        """
        feedback_list = []
        
        for filename in os.listdir(self.feedback_dir):
            if not filename.endswith('.json'):
                continue
            
            feedback_file = os.path.join(self.feedback_dir, filename)
            with open(feedback_file, 'r', encoding='utf-8') as f:
                feedback = json.load(f)
            
            if filter_type and feedback['type'] != filter_type:
                continue
            
            feedback_list.append({
                'id': feedback['id'],
                'user_id': feedback['user_id'],
                'type': feedback['type'],
                'content': feedback['content'],
                'rating': feedback.get('rating'),
                'status': feedback['status'],
                'created_at': feedback['created_at'],
                'analysis': feedback.get('analysis', {})
            })
        
        # 按创建时间排序
        feedback_list.sort(key=lambda x: x['created_at'], reverse=True)
        
        return feedback_list
    
    def update_feedback_status(self, feedback_id, status):
        """
        更新反馈状态
        
        Args:
            feedback_id (str): 反馈ID
            status (str): 新状态
        
        Returns:
            bool: 更新是否成功
        """
        feedback_file = os.path.join(self.feedback_dir, f"{feedback_id}.json")
        if not os.path.exists(feedback_file):
            return False
        
        with open(feedback_file, 'r', encoding='utf-8') as f:
            feedback = json.load(f)
        
        feedback['status'] = status
        
        with open(feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback, f, ensure_ascii=False, indent=2)
        
        return True
    
    def optimize_interface(self, interface_name, improvements):
        """
        优化界面
        
        Args:
            interface_name (str): 界面名称
            improvements (dict): 改进内容
        
        Returns:
            str: 优化ID
        """
        # 生成优化ID
        optimization_id = f"optimization_{int(time.time())}"
        
        # 创建优化文件
        optimization_file = os.path.join(self.interface_dir, f"{optimization_id}.json")
        optimization = {
            'id': optimization_id,
            'interface_name': interface_name,
            'improvements': improvements,
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        with open(optimization_file, 'w', encoding='utf-8') as f:
            json.dump(optimization, f, ensure_ascii=False, indent=2)
        
        # 更新统计数据
        stats = self._load_stats()
        stats['interface_improvements'] += 1
        self._save_stats(stats)
        
        return optimization_id
    
    def get_interface_optimizations(self, interface_name=None):
        """
        获取界面优化记录
        
        Args:
            interface_name (str): 界面名称
        
        Returns:
            list: 优化记录列表
        """
        optimizations = []
        
        for filename in os.listdir(self.interface_dir):
            if not filename.endswith('.json'):
                continue
            
            optimization_file = os.path.join(self.interface_dir, filename)
            with open(optimization_file, 'r', encoding='utf-8') as f:
                optimization = json.load(f)
            
            if interface_name and optimization['interface_name'] != interface_name:
                continue
            
            optimizations.append(optimization)
        
        # 按创建时间排序
        optimizations.sort(key=lambda x: x['created_at'], reverse=True)
        
        return optimizations
    
    def get_stats(self):
        """
        获取用户体验统计信息
        
        Returns:
            dict: 统计信息
        """
        return self._load_stats()
    
    def generate_feedback_report(self, period='month'):
        """
        生成反馈报告
        
        Args:
            period (str): 报告周期 (week, month, year)
        
        Returns:
            dict: 反馈报告
        """
        # 收集反馈数据
        feedback_list = self.list_feedback()
        
        # 统计数据
        total_feedback = len(feedback_list)
        feedback_by_type = {}
        feedback_by_category = {}
        feedback_by_sentiment = {}
        feedback_by_priority = {}
        
        for feedback in feedback_list:
            # 按类型统计
            feedback_type = feedback['type']
            if feedback_type not in feedback_by_type:
                feedback_by_type[feedback_type] = 0
            feedback_by_type[feedback_type] += 1
            
            # 按分类统计
            if 'analysis' in feedback and 'category' in feedback['analysis']:
                category = feedback['analysis']['category']
                if category not in feedback_by_category:
                    feedback_by_category[category] = 0
                feedback_by_category[category] += 1
            
            # 按情感统计
            if 'analysis' in feedback and 'sentiment' in feedback['analysis']:
                sentiment = feedback['analysis']['sentiment']
                if sentiment not in feedback_by_sentiment:
                    feedback_by_sentiment[sentiment] = 0
                feedback_by_sentiment[sentiment] += 1
            
            # 按优先级统计
            if 'analysis' in feedback and 'priority' in feedback['analysis']:
                priority = feedback['analysis']['priority']
                if priority not in feedback_by_priority:
                    feedback_by_priority[priority] = 0
                feedback_by_priority[priority] += 1
        
        # 生成报告
        report = {
            'id': f"report_{int(time.time())}",
            'generated_at': datetime.now().isoformat(),
            'period': period,
            'total_feedback': total_feedback,
            'feedback_by_type': feedback_by_type,
            'feedback_by_category': feedback_by_category,
            'feedback_by_sentiment': feedback_by_sentiment,
            'feedback_by_priority': feedback_by_priority,
            'user_satisfaction': self._load_stats()['user_satisfaction'],
            'recommendations': self._generate_recommendations(feedback_list)
        }
        
        return report
    
    def _generate_recommendations(self, feedback_list):
        """生成改进建议"""
        recommendations = []
        
        # 分析高频问题
        issue_counts = {}
        for feedback in feedback_list:
            if feedback['type'] in ['bug', 'suggestion']:
                content = feedback['content'].lower()
                # 简单的问题提取
                if 'slow' in content or 'lag' in content:
                    issue = 'performance'
                elif 'ui' in content or 'interface' in content:
                    issue = 'ui'
                elif 'error' in content or 'crash' in content:
                    issue = 'stability'
                elif 'workflow' in content or 'process' in content:
                    issue = 'workflow'
                else:
                    issue = 'other'
                
                if issue not in issue_counts:
                    issue_counts[issue] = 0
                issue_counts[issue] += 1
        
        # 生成建议
        if issue_counts.get('performance', 0) > 3:
            recommendations.append('优化系统性能，特别是在处理大型任务时')
        if issue_counts.get('ui', 0) > 3:
            recommendations.append('改进用户界面，提高易用性和美观度')
        if issue_counts.get('stability', 0) > 3:
            recommendations.append('增强系统稳定性，减少崩溃和错误')
        if issue_counts.get('workflow', 0) > 3:
            recommendations.append('优化工作流程，提高用户效率')
        
        return recommendations

if __name__ == '__main__':
    # 测试用户体验管理器
    print("测试用户体验管理器")
    ux_manager = UserExperienceManager()
    
    # 收集反馈
    print("\n收集用户反馈")
    feedback_id1 = ux_manager.collect_feedback(
        user_id="user_001",
        feedback_type="bug",
        content="系统在处理大型项目时运行速度很慢",
        rating=2,
        context={"project_size": "large", "action": "code_analysis"}
    )
    print(f"添加反馈1: {feedback_id1}")
    
    feedback_id2 = ux_manager.collect_feedback(
        user_id="user_002",
        feedback_type="feature",
        content="希望添加更多的可视化功能",
        rating=4,
        context={"role": "architect", "use_case": "system_design"}
    )
    print(f"添加反馈2: {feedback_id2}")
    
    feedback_id3 = ux_manager.collect_feedback(
        user_id="user_003",
        feedback_type="suggestion",
        content="界面布局可以更简洁一些",
        rating=3,
        context={"interface": "dashboard", "device": "desktop"}
    )
    print(f"添加反馈3: {feedback_id3}")
    
    # 列出反馈
    print("\n列出反馈")
    feedback_list = ux_manager.list_feedback()
    print(f"总反馈数: {len(feedback_list)}")
    for feedback in feedback_list:
        print(f"- {feedback['id']}: {feedback['type']} (评分: {feedback.get('rating')})")
        print(f"  内容: {feedback['content']}")
        if 'analysis' in feedback and feedback['analysis']:
            print(f"  分析: 分类={feedback['analysis'].get('category')}, 情感={feedback['analysis'].get('sentiment')}, 优先级={feedback['analysis'].get('priority')}")
    
    # 优化界面
    print("\n优化界面")
    optimization_id = ux_manager.optimize_interface(
        interface_name="dashboard",
        improvements={
            "layout": "更简洁的布局，减少视觉干扰",
            "navigation": "简化导航结构，提高可访问性",
            "performance": "优化页面加载速度",
            "usability": "改进交互体验，增加操作反馈"
        }
    )
    print(f"添加界面优化: {optimization_id}")
    
    # 获取界面优化记录
    print("\n获取界面优化记录")
    optimizations = ux_manager.get_interface_optimizations("dashboard")
    for optimization in optimizations:
        print(f"- {optimization['id']}: {optimization['interface_name']}")
        print("  改进内容:")
        for key, value in optimization['improvements'].items():
            print(f"    {key}: {value}")
    
    # 生成反馈报告
    print("\n生成反馈报告")
    report = ux_manager.generate_feedback_report()
    print(f"报告ID: {report['id']}")
    print(f"生成时间: {report['generated_at']}")
    print(f"总反馈数: {report['total_feedback']}")
    print("反馈类型分布:")
    for type_, count in report['feedback_by_type'].items():
        print(f"- {type_}: {count}")
    print(f"用户满意度: {report['user_satisfaction']:.1f}/5")
    print("改进建议:")
    for recommendation in report['recommendations']:
        print(f"- {recommendation}")
    
    # 获取统计信息
    print("\n用户体验统计信息")
    stats = ux_manager.get_stats()
    print(f"总反馈数: {stats['feedback_count']}")
    print(f"界面改进数: {stats['interface_improvements']}")
    print(f"用户满意度: {stats['user_satisfaction']:.1f}/5")
    print("反馈类型分布:")
    for type_, count in stats['feedback_categories'].items():
        print(f"- {type_}: {count}")

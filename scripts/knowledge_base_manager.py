#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业领域知识库管理器

用于存储、管理和检索专业领域知识，支持基于关键词的搜索和知识结构化。
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path

class KnowledgeBaseManager:
    """知识库管理器类"""
    
    def __init__(self, knowledge_base_path=None):
        """
        初始化知识库管理器
        
        Args:
            knowledge_base_path (str): 知识库路径
        """
        self.knowledge_base_path = knowledge_base_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'memory-bank',
            'knowledge_base'
        )
        self.domains_dir = os.path.join(self.knowledge_base_path, 'domains')
        self.index_path = os.path.join(self.knowledge_base_path, 'index.json')
        os.makedirs(self.domains_dir, exist_ok=True)
        self._init_index()
    
    def _init_index(self):
        """初始化知识库索引"""
        if not os.path.exists(self.index_path):
            index = {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'domains': {},
                'total_documents': 0
            }
            self._save_index(index)
    
    def _load_index(self):
        """加载知识库索引"""
        with open(self.index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_index(self, index):
        """保存知识库索引"""
        index['last_updated'] = datetime.now().isoformat()
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    
    def add_knowledge(self, domain, title, content, tags=None):
        """
        添加知识到知识库
        
        Args:
            domain (str): 知识领域
            title (str): 知识标题
            content (str): 知识内容
            tags (list): 标签列表
        
        Returns:
            str: 知识ID
        """
        # 生成知识ID
        knowledge_id = f"knowledge_{int(time.time())}"
        
        # 创建领域目录
        domain_dir = os.path.join(self.domains_dir, domain)
        os.makedirs(domain_dir, exist_ok=True)
        
        # 创建知识文件
        knowledge_file = os.path.join(domain_dir, f"{knowledge_id}.json")
        knowledge = {
            'id': knowledge_id,
            'domain': domain,
            'title': title,
            'content': content,
            'tags': tags or [],
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
        
        with open(knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge, f, ensure_ascii=False, indent=2)
        
        # 更新索引
        index = self._load_index()
        if domain not in index['domains']:
            index['domains'][domain] = {
                'count': 0,
                'documents': []
            }
        index['domains'][domain]['count'] += 1
        index['domains'][domain]['documents'].append(knowledge_id)
        index['total_documents'] += 1
        self._save_index(index)
        
        return knowledge_id
    
    def get_knowledge(self, knowledge_id):
        """
        获取知识内容
        
        Args:
            knowledge_id (str): 知识ID
        
        Returns:
            dict: 知识内容
        """
        # 搜索所有领域目录
        for domain in os.listdir(self.domains_dir):
            domain_dir = os.path.join(self.domains_dir, domain)
            if not os.path.isdir(domain_dir):
                continue
            
            knowledge_file = os.path.join(domain_dir, f"{knowledge_id}.json")
            if os.path.exists(knowledge_file):
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        return None
    
    def search_knowledge(self, keyword, domains=None):
        """
        搜索知识
        
        Args:
            keyword (str): 搜索关键词
            domains (list): 限定搜索的领域
        
        Returns:
            list: 搜索结果
        """
        results = []
        keyword_lower = keyword.lower()
        
        # 确定要搜索的领域
        if domains:
            search_domains = domains
        else:
            search_domains = os.listdir(self.domains_dir)
        
        # 搜索每个领域
        for domain in search_domains:
            domain_dir = os.path.join(self.domains_dir, domain)
            if not os.path.isdir(domain_dir):
                continue
            
            # 搜索领域内的所有知识
            for filename in os.listdir(domain_dir):
                if not filename.endswith('.json'):
                    continue
                
                knowledge_file = os.path.join(domain_dir, filename)
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    knowledge = json.load(f)
                
                # 检查关键词是否在标题、内容或标签中
                if (keyword_lower in knowledge['title'].lower() or 
                    keyword_lower in knowledge['content'].lower() or 
                    any(keyword_lower in tag.lower() for tag in knowledge['tags'])):
                    results.append({
                        'id': knowledge['id'],
                        'domain': knowledge['domain'],
                        'title': knowledge['title'],
                        'relevance': self._calculate_relevance(knowledge, keyword_lower),
                        'created_at': knowledge['created_at']
                    })
        
        # 按相关性排序
        results.sort(key=lambda x: x['relevance'], reverse=True)
        
        return results
    
    def _calculate_relevance(self, knowledge, keyword):
        """
        计算知识与关键词的相关性
        
        Args:
            knowledge (dict): 知识内容
            keyword (str): 关键词
        
        Returns:
            float: 相关性得分
        """
        relevance = 0.0
        
        # 标题匹配权重最高
        if keyword in knowledge['title'].lower():
            relevance += 3.0
        
        # 内容匹配权重次之
        if keyword in knowledge['content'].lower():
            relevance += 2.0
        
        # 标签匹配权重较低
        if any(keyword in tag.lower() for tag in knowledge['tags']):
            relevance += 1.0
        
        return relevance
    
    def list_domains(self):
        """
        列出所有知识领域
        
        Returns:
            list: 领域列表
        """
        index = self._load_index()
        return list(index['domains'].keys())
    
    def get_domain_stats(self, domain):
        """
        获取领域统计信息
        
        Args:
            domain (str): 领域名称
        
        Returns:
            dict: 领域统计信息
        """
        index = self._load_index()
        if domain in index['domains']:
            return index['domains'][domain]
        return None
    
    def update_knowledge(self, knowledge_id, updates):
        """
        更新知识
        
        Args:
            knowledge_id (str): 知识ID
            updates (dict): 更新内容
        
        Returns:
            bool: 更新是否成功
        """
        # 搜索知识文件
        for domain in os.listdir(self.domains_dir):
            domain_dir = os.path.join(self.domains_dir, domain)
            if not os.path.isdir(domain_dir):
                continue
            
            knowledge_file = os.path.join(domain_dir, f"{knowledge_id}.json")
            if os.path.exists(knowledge_file):
                # 加载并更新知识
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    knowledge = json.load(f)
                
                knowledge.update(updates)
                knowledge['last_updated'] = datetime.now().isoformat()
                
                # 保存更新后的知识
                with open(knowledge_file, 'w', encoding='utf-8') as f:
                    json.dump(knowledge, f, ensure_ascii=False, indent=2)
                
                return True
        
        return False
    
    def delete_knowledge(self, knowledge_id):
        """
        删除知识
        
        Args:
            knowledge_id (str): 知识ID
        
        Returns:
            bool: 删除是否成功
        """
        # 搜索知识文件
        for domain in os.listdir(self.domains_dir):
            domain_dir = os.path.join(self.domains_dir, domain)
            if not os.path.isdir(domain_dir):
                continue
            
            knowledge_file = os.path.join(domain_dir, f"{knowledge_id}.json")
            if os.path.exists(knowledge_file):
                # 删除文件
                os.remove(knowledge_file)
                
                # 更新索引
                index = self._load_index()
                if domain in index['domains']:
                    if knowledge_id in index['domains'][domain]['documents']:
                        index['domains'][domain]['documents'].remove(knowledge_id)
                        index['domains'][domain]['count'] -= 1
                        index['total_documents'] -= 1
                        self._save_index(index)
                
                return True
        
        return False
    
    def import_knowledge(self, domain, file_path):
        """
        从文件导入知识
        
        Args:
            domain (str): 知识领域
            file_path (str): 文件路径
        
        Returns:
            list: 导入的知识ID列表
        """
        imported_ids = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            knowledge_items = json.load(f)
        
        for item in knowledge_items:
            knowledge_id = self.add_knowledge(
                domain=domain,
                title=item.get('title', ''),
                content=item.get('content', ''),
                tags=item.get('tags', [])
            )
            imported_ids.append(knowledge_id)
        
        return imported_ids
    
    def export_knowledge(self, domain, output_path):
        """
        导出知识到文件
        
        Args:
            domain (str): 知识领域
            output_path (str): 输出文件路径
        
        Returns:
            bool: 导出是否成功
        """
        domain_dir = os.path.join(self.domains_dir, domain)
        if not os.path.exists(domain_dir):
            return False
        
        knowledge_items = []
        for filename in os.listdir(domain_dir):
            if not filename.endswith('.json'):
                continue
            
            knowledge_file = os.path.join(domain_dir, filename)
            with open(knowledge_file, 'r', encoding='utf-8') as f:
                knowledge = json.load(f)
            knowledge_items.append(knowledge)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_items, f, ensure_ascii=False, indent=2)
        
        return True
    
    def get_stats(self):
        """
        获取知识库统计信息
        
        Returns:
            dict: 统计信息
        """
        index = self._load_index()
        stats = {
            'total_documents': index['total_documents'],
            'total_domains': len(index['domains']),
            'domains': {},
            'last_updated': index['last_updated']
        }
        
        for domain, info in index['domains'].items():
            stats['domains'][domain] = info['count']
        
        return stats

if __name__ == '__main__':
    # 测试知识库管理器
    print("测试知识库管理器")
    manager = KnowledgeBaseManager()
    
    # 添加知识
    print("\n添加知识")
    knowledge_id1 = manager.add_knowledge(
        domain="AI安全",
        title="对抗攻击防御算法",
        content="对抗攻击是指通过对输入数据进行微小扰动，导致模型输出错误结果的攻击方式。常见的防御方法包括：1. 对抗训练 2. 输入净化 3. 模型集成 4. 梯度掩盖",
        tags=["AI安全", "对抗攻击", "防御算法"]
    )
    print(f"添加知识1: {knowledge_id1}")
    
    knowledge_id2 = manager.add_knowledge(
        domain="神经网络",
        title="dtype不匹配问题",
        content="dtype不匹配是指在神经网络训练过程中，不同张量的数据类型不一致导致的问题。常见的解决方法包括：1. 统一数据类型 2. 使用自动类型转换 3. 显式类型转换",
        tags=["神经网络", "dtype", "类型不匹配"]
    )
    print(f"添加知识2: {knowledge_id2}")
    
    knowledge_id3 = manager.add_knowledge(
        domain="架构设计",
        title="政务合规要求",
        content="政务系统架构设计需要考虑的合规要求包括：1. 数据安全 2. 隐私保护 3. 审计日志 4. 访问控制 5. 国产化要求 6. 等级保护",
        tags=["架构设计", "政务合规", "安全要求"]
    )
    print(f"添加知识3: {knowledge_id3}")
    
    # 列出领域
    print("\n列出领域")
    domains = manager.list_domains()
    for domain in domains:
        stats = manager.get_domain_stats(domain)
        print(f"- {domain}: {stats['count']} 条知识")
    
    # 搜索知识
    print("\n搜索知识")
    results = manager.search_knowledge("安全")
    print(f"搜索 '安全' 结果: {len(results)} 条")
    for result in results:
        print(f"- {result['title']} (相关度: {result['relevance']:.2f})")
    
    # 获取知识详情
    print("\n获取知识详情")
    knowledge = manager.get_knowledge(knowledge_id1)
    if knowledge:
        print(f"知识标题: {knowledge['title']}")
        print(f"领域: {knowledge['domain']}")
        print(f"内容: {knowledge['content']}")
        print(f"标签: {', '.join(knowledge['tags'])}")
    
    # 更新知识
    print("\n更新知识")
    update_success = manager.update_knowledge(
        knowledge_id1,
        {"content": "对抗攻击是指通过对输入数据进行微小扰动，导致模型输出错误结果的攻击方式。常见的防御方法包括：1. 对抗训练 2. 输入净化 3. 模型集成 4. 梯度掩盖 5. 随机化输入"}
    )
    print(f"更新成功: {update_success}")
    
    # 再次获取知识详情
    updated_knowledge = manager.get_knowledge(knowledge_id1)
    if updated_knowledge:
        print(f"更新后的内容: {updated_knowledge['content']}")
    
    # 获取统计信息
    print("\n知识库统计信息")
    stats = manager.get_stats()
    print(f"总知识数: {stats['total_documents']}")
    print(f"总领域数: {stats['total_domains']}")
    print("各领域知识数:")
    for domain, count in stats['domains'].items():
        print(f"- {domain}: {count}")
    print(f"最后更新时间: {stats['last_updated']}")

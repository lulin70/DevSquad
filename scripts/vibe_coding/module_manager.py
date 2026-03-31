#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding 模块化设计工具

实现模块化设计功能，包括模块管理器和API接口。
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

class ModuleType(Enum):
    """模块类型"""
    API = "api"              # API模块
    SERVICE = "service"      # 服务模块
    COMPONENT = "component"  # 组件模块
    UTIL = "util"            # 工具模块
    MODEL = "model"          # 模型模块
    CONFIG = "config"        # 配置模块
    TEST = "test"            # 测试模块
    DOCS = "docs"            # 文档模块

class ModuleStatus(Enum):
    """模块状态"""
    PLANNING = "planning"    # 规划中
    DEVELOPING = "developing"  # 开发中
    TESTING = "testing"      # 测试中
    COMPLETED = "completed"   # 已完成
    DEPRECATED = "deprecated"  # 已废弃

@dataclass
class ModuleDependency:
    """模块依赖"""
    module_id: str
    version: str
    dependency_type: str  # runtime, dev, test
    optional: bool = False

@dataclass
class ModuleInterface:
    """模块接口"""
    interface_id: str
    name: str
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    methods: List[str]

@dataclass
class Module:
    """模块"""
    module_id: str
    name: str
    description: str
    module_type: ModuleType
    status: ModuleStatus
    version: str
    dependencies: List[ModuleDependency] = field(default_factory=list)
    interfaces: List[ModuleInterface] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    author: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ModuleConfig:
    """模块配置"""
    config_id: str
    module_id: str
    config_type: str
    config_data: Dict[str, Any]
    environment: str = "default"  # development, production, testing
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

class ModuleManager:
    """模块管理器"""
    
    def __init__(self, project_root: str = "."):
        """
        初始化模块管理器
        
        Args:
            project_root: 项目根目录
        """
        self.project_root = Path(project_root)
        self.modules_dir = self.project_root / "modules"
        self.configs_dir = self.project_root / "configs"
        os.makedirs(self.modules_dir, exist_ok=True)
        os.makedirs(self.configs_dir, exist_ok=True)
        
        # 模块存储
        self.modules: Dict[str, Module] = {}
        self.configs: Dict[str, ModuleConfig] = {}
        
        # 加载现有模块
        self._load_modules()
        self._load_configs()
    
    def _load_modules(self):
        """加载模块"""
        if not self.modules_dir.exists():
            return
        
        for filename in os.listdir(self.modules_dir):
            if filename.endswith('.json'):
                module_file = self.modules_dir / filename
                try:
                    with open(module_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 恢复模块数据
                    module_type = ModuleType(data['module_type'])
                    status = ModuleStatus(data['status'])
                    dependencies = []
                    for dep_data in data.get('dependencies', []):
                        dependency = ModuleDependency(**dep_data)
                        dependencies.append(dependency)
                    
                    interfaces = []
                    for iface_data in data.get('interfaces', []):
                        interface = ModuleInterface(**iface_data)
                        interfaces.append(interface)
                    
                    module = Module(
                        module_id=data['module_id'],
                        name=data['name'],
                        description=data['description'],
                        module_type=module_type,
                        status=status,
                        version=data['version'],
                        dependencies=dependencies,
                        interfaces=interfaces,
                        files=data.get('files', []),
                        author=data.get('author', ''),
                        created_at=data.get('created_at'),
                        updated_at=data.get('updated_at')
                    )
                    
                    self.modules[module.module_id] = module
                    
                except Exception as e:
                    print(f"加载模块失败 {filename}：{e}")
    
    def _load_configs(self):
        """加载配置"""
        if not self.configs_dir.exists():
            return
        
        for filename in os.listdir(self.configs_dir):
            if filename.endswith('.json'):
                config_file = self.configs_dir / filename
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    config = ModuleConfig(**data)
                    self.configs[config.config_id] = config
                    
                except Exception as e:
                    print(f"加载配置失败 {filename}：{e}")
    
    def create_module(self, module_data: Dict[str, Any]) -> Module:
        """
        创建模块
        
        Args:
            module_data: 模块数据
        
        Returns:
            Module: 创建的模块
        """
        # 生成模块ID
        module_id = module_data.get('module_id') or f"module_{int(time.time())}"
        
        # 创建模块
        module = Module(
            module_id=module_id,
            name=module_data['name'],
            description=module_data['description'],
            module_type=ModuleType(module_data['module_type']),
            status=ModuleStatus(module_data.get('status', 'planning')),
            version=module_data.get('version', '1.0.0'),
            author=module_data.get('author', '')
        )
        
        # 添加依赖
        if 'dependencies' in module_data:
            for dep_data in module_data['dependencies']:
                dependency = ModuleDependency(**dep_data)
                module.dependencies.append(dependency)
        
        # 添加接口
        if 'interfaces' in module_data:
            for iface_data in module_data['interfaces']:
                interface = ModuleInterface(**iface_data)
                module.interfaces.append(interface)
        
        # 保存模块
        self.save_module(module)
        
        return module
    
    def save_module(self, module: Module):
        """
        保存模块
        
        Args:
            module: 模块
        """
        module.updated_at = datetime.now().isoformat()
        
        # 保存到文件
        module_file = self.modules_dir / f"{module.module_id}.json"
        
        # 转换枚举为字符串
        module_data = asdict(module)
        module_data['module_type'] = module.module_type.value
        module_data['status'] = module.status.value
        
        with open(module_file, 'w', encoding='utf-8') as f:
            json.dump(module_data, f, ensure_ascii=False, indent=2)
        
        # 更新内存中的模块
        self.modules[module.module_id] = module
    
    def get_module(self, module_id: str) -> Optional[Module]:
        """
        获取模块
        
        Args:
            module_id: 模块ID
        
        Returns:
            Module: 模块
        """
        return self.modules.get(module_id)
    
    def list_modules(self, module_type: ModuleType = None) -> List[Module]:
        """
        列出模块
        
        Args:
            module_type: 模块类型
        
        Returns:
            List[Module]: 模块列表
        """
        modules = list(self.modules.values())
        
        if module_type:
            modules = [m for m in modules if m.module_type == module_type]
        
        # 按创建时间排序
        modules.sort(key=lambda x: x.created_at, reverse=True)
        
        return modules
    
    def update_module_status(self, module_id: str, status: ModuleStatus):
        """
        更新模块状态
        
        Args:
            module_id: 模块ID
            status: 新状态
        """
        module = self.get_module(module_id)
        if module:
            module.status = status
            self.save_module(module)
    
    def add_module_dependency(self, module_id: str, dependency: ModuleDependency):
        """
        添加模块依赖
        
        Args:
            module_id: 模块ID
            dependency: 依赖
        """
        module = self.get_module(module_id)
        if module:
            # 检查是否已存在相同依赖
            existing = [d for d in module.dependencies if d.module_id == dependency.module_id]
            if not existing:
                module.dependencies.append(dependency)
                self.save_module(module)
    
    def add_module_interface(self, module_id: str, interface: ModuleInterface):
        """
        添加模块接口
        
        Args:
            module_id: 模块ID
            interface: 接口
        """
        module = self.get_module(module_id)
        if module:
            # 检查是否已存在相同接口
            existing = [i for i in module.interfaces if i.interface_id == interface.interface_id]
            if not existing:
                module.interfaces.append(interface)
                self.save_module(module)
    
    def remove_module(self, module_id: str):
        """
        删除模块
        
        Args:
            module_id: 模块ID
        """
        if module_id in self.modules:
            # 删除文件
            module_file = self.modules_dir / f"{module_id}.json"
            if module_file.exists():
                os.remove(module_file)
            
            # 从内存中删除
            del self.modules[module_id]
    
    def create_config(self, config_data: Dict[str, Any]) -> ModuleConfig:
        """
        创建配置
        
        Args:
            config_data: 配置数据
        
        Returns:
            ModuleConfig: 创建的配置
        """
        # 生成配置ID
        config_id = config_data.get('config_id') or f"config_{int(time.time())}"
        
        # 创建配置
        config = ModuleConfig(
            config_id=config_id,
            module_id=config_data['module_id'],
            config_type=config_data['config_type'],
            config_data=config_data['config_data'],
            environment=config_data.get('environment', 'default')
        )
        
        # 保存配置
        self.save_config(config)
        
        return config
    
    def save_config(self, config: ModuleConfig):
        """
        保存配置
        
        Args:
            config: 配置
        """
        # 保存到文件
        config_file = self.configs_dir / f"{config.config_id}.json"
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(config), f, ensure_ascii=False, indent=2)
        
        # 更新内存中的配置
        self.configs[config.config_id] = config
    
    def get_config(self, config_id: str) -> Optional[ModuleConfig]:
        """
        获取配置
        
        Args:
            config_id: 配置ID
        
        Returns:
            ModuleConfig: 配置
        """
        return self.configs.get(config_id)
    
    def list_configs(self, module_id: str = None) -> List[ModuleConfig]:
        """
        列出配置
        
        Args:
            module_id: 模块ID
        
        Returns:
            List[ModuleConfig]: 配置列表
        """
        configs = list(self.configs.values())
        
        if module_id:
            configs = [c for c in configs if c.module_id == module_id]
        
        # 按创建时间排序
        configs.sort(key=lambda x: x.created_at, reverse=True)
        
        return configs
    
    def analyze_dependencies(self, module_id: str) -> Dict[str, Any]:
        """
        分析模块依赖
        
        Args:
            module_id: 模块ID
        
        Returns:
            Dict[str, Any]: 依赖分析结果
        """
        module = self.get_module(module_id)
        if not module:
            return {}
        
        dependencies = []
        for dep in module.dependencies:
            dep_module = self.get_module(dep.module_id)
            if dep_module:
                dependencies.append({
                    'module_id': dep.module_id,
                    'name': dep_module.name,
                    'version': dep.version,
                    'dependency_type': dep.dependency_type,
                    'optional': dep.optional,
                    'status': dep_module.status.value
                })
        
        return {
            'module_id': module_id,
            'name': module.name,
            'dependencies': dependencies,
            'dependency_count': len(dependencies)
        }
    
    def generate_module_structure(self, module_id: str) -> Dict[str, Any]:
        """
        生成模块结构
        
        Args:
            module_id: 模块ID
        
        Returns:
            Dict[str, Any]: 模块结构
        """
        module = self.get_module(module_id)
        if not module:
            return {}
        
        # 生成目录结构
        structure = {
            'module_id': module_id,
            'name': module.name,
            'type': module.module_type.value,
            'version': module.version,
            'directories': [],
            'files': []
        }
        
        # 根据模块类型生成目录结构
        if module.module_type == ModuleType.API:
            structure['directories'] = [
                'src/api',
                'src/models',
                'src/services',
                'tests/api'
            ]
            structure['files'] = [
                'src/api/__init__.py',
                'src/api/routes.py',
                'src/models/__init__.py',
                'src/services/__init__.py',
                'tests/api/test_routes.py',
                'README.md',
                'setup.py'
            ]
        elif module.module_type == ModuleType.SERVICE:
            structure['directories'] = [
                'src/service',
                'src/utils',
                'tests/service'
            ]
            structure['files'] = [
                'src/service/__init__.py',
                'src/service/main.py',
                'src/utils/__init__.py',
                'tests/service/test_service.py',
                'README.md',
                'setup.py'
            ]
        elif module.module_type == ModuleType.COMPONENT:
            structure['directories'] = [
                'src/component',
                'src/styles',
                'tests/component'
            ]
            structure['files'] = [
                'src/component/__init__.py',
                'src/component/main.py',
                'src/styles/__init__.py',
                'tests/component/test_component.py',
                'README.md',
                'setup.py'
            ]
        elif module.module_type == ModuleType.UTIL:
            structure['directories'] = [
                'src/util',
                'tests/util'
            ]
            structure['files'] = [
                'src/util/__init__.py',
                'src/util/main.py',
                'tests/util/test_util.py',
                'README.md',
                'setup.py'
            ]
        
        return structure

if __name__ == '__main__':
    """示例用法"""
    # 创建模块管理器
    manager = ModuleManager(project_root=".")
    
    # 创建API模块
    api_module = manager.create_module({
        'name': '用户API',
        'description': '用户管理API模块',
        'module_type': 'api',
        'status': 'planning',
        'version': '1.0.0',
        'author': 'Vibe Coding Team'
    })
    
    # 添加依赖
    manager.add_module_dependency(api_module.module_id, ModuleDependency(
        module_id='module_user_service',
        version='1.0.0',
        dependency_type='runtime'
    ))
    
    # 添加接口
    manager.add_module_interface(api_module.module_id, ModuleInterface(
        interface_id='user_api_interface',
        name='用户API接口',
        description='用户管理相关的API接口',
        inputs={'user_id': 'string', 'name': 'string'}, 
        outputs={'success': 'boolean', 'user': 'object'},
        methods=['GET', 'POST', 'PUT', 'DELETE']
    ))
    
    # 更新模块状态
    manager.update_module_status(api_module.module_id, ModuleStatus.DEVELOPING)
    
    # 创建服务模块
    service_module = manager.create_module({
        'name': '用户服务',
        'description': '用户管理服务模块',
        'module_type': 'service',
        'status': 'planning',
        'version': '1.0.0',
        'author': 'Vibe Coding Team'
    })
    
    # 列出所有模块
    modules = manager.list_modules()
    print("所有模块:")
    for module in modules:
        print(f"- {module.module_id}: {module.name} ({module.module_type.value}) - {module.status.value}")
    
    # 分析依赖
    dependency_analysis = manager.analyze_dependencies(api_module.module_id)
    print("\n依赖分析:")
    print(f"模块: {dependency_analysis['name']}")
    print("依赖:")
    for dep in dependency_analysis['dependencies']:
        print(f"  - {dep['name']} ({dep['version']}) - {dep['status']}")
    
    # 生成模块结构
    structure = manager.generate_module_structure(api_module.module_id)
    print("\n模块结构:")
    print(f"模块: {structure['name']}")
    print("目录:")
    for directory in structure['directories']:
        print(f"  - {directory}")
    print("文件:")
    for file in structure['files']:
        print(f"  - {file}")

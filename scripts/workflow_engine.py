#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流编排引擎

提供灵活的工作流定义、执行和监控功能
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str
    name: str
    description: str
    role_id: str  # 负责的角色
    action: str  # 执行的动作
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)  # 执行条件
    timeout: int = 3600  # 超时时间（秒）
    retry_count: int = 3  # 重试次数
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class WorkflowDefinition:
    """工作流定义"""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)  # 全局变量
    conditions: Dict[str, Any] = field(default_factory=dict)  # 全局条件
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class WorkflowInstance:
    """工作流实例"""
    instance_id: str
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: str = ""


class WorkflowEngine:
    """
    工作流编排引擎
    
    功能：
    - 工作流定义和管理
    - 步骤执行和调度
    - 条件分支和循环
    - 错误处理和重试
    - 进度跟踪和监控
    """
    
    def __init__(self, storage_path: str = "."):
        """
        初始化工作流引擎
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = Path(storage_path) / "workflows"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 工作流定义
        self.definitions: Dict[str, WorkflowDefinition] = {}
        
        # 工作流实例
        self.instances: Dict[str, WorkflowInstance] = {}
        
        # 步骤执行器（注册的动作处理函数）
        self.executors: Dict[str, Callable] = {}
        
        # 加载现有工作流
        self._load()
    
    def _load(self):
        """从磁盘加载工作流定义"""
        workflows_file = self.storage_path / "definitions.json"
        if workflows_file.exists():
            try:
                with open(workflows_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for wf_id, wf_data in data.get('definitions', {}).items():
                    # 恢复步骤
                    steps = []
                    for step_data in wf_data.get('steps', []):
                        step = WorkflowStep(
                            step_id=step_data['step_id'],
                            name=step_data['name'],
                            description=step_data['description'],
                            role_id=step_data['role_id'],
                            action=step_data['action'],
                            inputs=step_data.get('inputs', {}),
                            outputs=step_data.get('outputs', {}),
                            conditions=step_data.get('conditions', {}),
                            timeout=step_data.get('timeout', 3600),
                            retry_count=step_data.get('retry_count', 3),
                            status=StepStatus(step_data.get('status', 'pending'))
                        )
                        steps.append(step)
                    
                    definition = WorkflowDefinition(
                        workflow_id=wf_data['workflow_id'],
                        name=wf_data['name'],
                        description=wf_data['description'],
                        steps=steps,
                        variables=wf_data.get('variables', {}),
                        conditions=wf_data.get('conditions', {}),
                        metadata=wf_data.get('metadata', {})
                    )
                    self.definitions[wf_id] = definition
                
            except Exception as e:
                print(f"加载工作流定义失败：{e}")
    
    def _save(self):
        """保存到磁盘"""
        workflows_file = self.storage_path / "definitions.json"
        
        data = {
            'version': '1.0',
            'updated_at': datetime.now().isoformat(),
            'definitions': {}
        }
        
        for wf_id, definition in self.definitions.items():
            wf_dict = asdict(definition)
            # 转换步骤
            wf_dict['steps'] = [asdict(step) for step in definition.steps]
            data['definitions'][wf_id] = wf_dict
        
        try:
            with open(workflows_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存工作流定义失败：{e}")
    
    def register_executor(self, action: str, executor: Callable):
        """
        注册步骤执行器
        
        Args:
            action: 动作名称
            executor: 执行函数
        """
        self.executors[action] = executor
        print(f"✅ 执行器已注册：{action}")
    
    def create_definition(self, definition: WorkflowDefinition) -> bool:
        """
        创建工作流定义
        
        Args:
            definition: 工作流定义
            
        Returns:
            bool: 是否创建成功
        """
        if definition.workflow_id in self.definitions:
            print(f"⚠️  工作流已存在：{definition.workflow_id}")
            return False
        
        self.definitions[definition.workflow_id] = definition
        self._save()
        
        print(f"✅ 工作流已创建：{definition.name}")
        return True
    
    def get_definition(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """
        获取工作流定义
        
        Args:
            workflow_id: 工作流 ID
            
        Returns:
            Optional[WorkflowDefinition]: 工作流定义
        """
        return self.definitions.get(workflow_id)
    
    def list_definitions(self) -> List[WorkflowDefinition]:
        """列出所有工作流定义"""
        return list(self.definitions.values())
    
    def start_workflow(self, workflow_id: str, 
                      variables: Dict[str, Any] = None) -> Optional[WorkflowInstance]:
        """
        启动工作流
        
        Args:
            workflow_id: 工作流 ID
            variables: 初始变量
            
        Returns:
            Optional[WorkflowInstance]: 工作流实例
        """
        definition = self.definitions.get(workflow_id)
        if not definition:
            print(f"❌ 工作流不存在：{workflow_id}")
            return None
        
        # 创建实例
        instance_id = f"{workflow_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        instance = WorkflowInstance(
            instance_id=instance_id,
            workflow_id=workflow_id,
            variables=variables or {},
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now().isoformat()
        )
        
        self.instances[instance_id] = instance
        
        print(f"🚀 工作流已启动：{instance_id}")
        
        # 执行第一步
        self._execute_next_step(instance)
        
        return instance
    
    def _execute_next_step(self, instance: WorkflowInstance):
        """
        执行下一步
        
        Args:
            instance: 工作流实例
        """
        definition = self.definitions.get(instance.workflow_id)
        if not definition:
            return
        
        # 找到下一步
        next_step = None
        for step in definition.steps:
            if step.step_id not in instance.completed_steps and \
               step.step_id not in instance.failed_steps:
                next_step = step
                break
        
        if not next_step:
            # 所有步骤完成
            self._complete_workflow(instance)
            return
        
        # 检查条件
        if not self._check_conditions(next_step.conditions, instance):
            # 条件不满足，跳过
            next_step.status = StepStatus.SKIPPED
            instance.completed_steps.append(next_step.step_id)
            self._execute_next_step(instance)
            return
        
        # 执行步骤
        instance.current_step = next_step.step_id
        next_step.status = StepStatus.RUNNING
        next_step.started_at = datetime.now().isoformat()
        
        print(f"▶️  执行步骤：{next_step.name}")
        
        # 异步执行（简化为同步）
        try:
            result = self._execute_step(next_step, instance)
            next_step.status = StepStatus.COMPLETED
            next_step.result = result
            next_step.completed_at = datetime.now().isoformat()
            instance.completed_steps.append(next_step.step_id)
            
            # 继续执行下一步
            self._execute_next_step(instance)
        
        except Exception as e:
            print(f"❌ 步骤执行失败：{next_step.name} - {str(e)}")
            next_step.status = StepStatus.FAILED
            next_step.error = str(e)
            instance.failed_steps.append(next_step.step_id)
            
            # 重试逻辑
            if next_step.retry_count > 0:
                next_step.retry_count -= 1
                print(f"🔄 重试步骤：{next_step.name} (剩余{next_step.retry_count}次)")
                self._execute_next_step(instance)
            else:
                # 重试耗尽，失败
                instance.status = WorkflowStatus.FAILED
                instance.error = f"步骤 {next_step.name} 执行失败：{str(e)}"
    
    def _execute_step(self, step: WorkflowStep, 
                     instance: WorkflowInstance) -> Any:
        """
        执行步骤
        
        Args:
            step: 步骤
            instance: 工作流实例
            
        Returns:
            Any: 执行结果
        """
        # 查找执行器
        executor = self.executors.get(step.action)
        if not executor:
            raise Exception(f"未找到执行器：{step.action}")
        
        # 准备输入
        inputs = copy.deepcopy(step.inputs)
        
        # 替换变量
        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith('${'):
                var_name = value[2:-1]
                inputs[key] = instance.variables.get(var_name)
        
        # 执行
        result = executor(step, inputs, instance)
        
        # 保存输出
        step.outputs = result if isinstance(result, dict) else {'result': result}
        
        # 更新变量
        for key, value in step.outputs.items():
            instance.variables[key] = value
        
        return result
    
    def _check_conditions(self, conditions: Dict[str, Any], 
                         instance: WorkflowInstance) -> bool:
        """
        检查条件
        
        Args:
            conditions: 条件
            instance: 工作流实例
            
        Returns:
            bool: 是否满足条件
        """
        if not conditions:
            return True
        
        for key, expected in conditions.items():
            actual = instance.variables.get(key)
            if actual != expected:
                return False
        
        return True
    
    def _complete_workflow(self, instance: WorkflowInstance):
        """
        完成工作流
        
        Args:
            instance: 工作流实例
        """
        instance.status = WorkflowStatus.COMPLETED
        instance.completed_at = datetime.now().isoformat()
        instance.current_step = None
        
        print(f"✅ 工作流已完成：{instance.instance_id}")
    
    def pause_workflow(self, instance_id: str) -> bool:
        """
        暂停工作流
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            bool: 是否暂停成功
        """
        instance = self.instances.get(instance_id)
        if not instance or instance.status != WorkflowStatus.RUNNING:
            return False
        
        instance.status = WorkflowStatus.PAUSED
        print(f"⏸️  工作流已暂停：{instance_id}")
        return True
    
    def resume_workflow(self, instance_id: str) -> bool:
        """
        恢复工作流
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            bool: 是否恢复成功
        """
        instance = self.instances.get(instance_id)
        if not instance or instance.status != WorkflowStatus.PAUSED:
            return False
        
        instance.status = WorkflowStatus.RUNNING
        print(f"▶️  工作流已恢复：{instance_id}")
        
        # 继续执行
        self._execute_next_step(instance)
        return True
    
    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """获取工作流实例"""
        return self.instances.get(instance_id)
    
    def get_progress(self, instance_id: str) -> Dict[str, Any]:
        """
        获取进度
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            Dict: 进度信息
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return {'error': '实例不存在'}
        
        definition = self.definitions.get(instance.workflow_id)
        if not definition:
            return {'error': '工作流定义不存在'}
        
        total_steps = len(definition.steps)
        completed = len(instance.completed_steps)
        failed = len(instance.failed_steps)
        
        return {
            'instance_id': instance_id,
            'status': instance.status.value,
            'current_step': instance.current_step,
            'total_steps': total_steps,
            'completed': completed,
            'failed': failed,
            'progress': completed / max(total_steps, 1),
            'started_at': instance.started_at,
            'completed_at': instance.completed_at
        }
    
    def create_default_workflows(self):
        """创建默认工作流"""
        # 标准开发工作流
        standard_workflow = WorkflowDefinition(
            workflow_id="standard-dev-workflow",
            name="标准开发工作流",
            description="产品 → 架构 → 开发 → 测试的完整流程",
            steps=[
                WorkflowStep(
                    step_id="prd",
                    name="需求分析",
                    description="分析需求，编写 PRD",
                    role_id="product-manager",
                    action="analyze_requirements",
                    inputs={"detail_level": "high"},
                    outputs={"prd": None}
                ),
                WorkflowStep(
                    step_id="architecture",
                    name="架构设计",
                    description="设计系统架构",
                    role_id="architect",
                    action="design_architecture",
                    inputs={"requirements": "${prd}"},
                    outputs={"architecture": None}
                ),
                WorkflowStep(
                    step_id="development",
                    name="代码开发",
                    description="实现功能代码",
                    role_id="developer",
                    action="implement_code",
                    inputs={"design": "${architecture}"},
                    outputs={"code": None}
                ),
                WorkflowStep(
                    step_id="testing",
                    name="测试验证",
                    description="执行测试用例",
                    role_id="tester",
                    action="execute_tests",
                    inputs={"code": "${code}"},
                    outputs={"test_results": None}
                )
            ]
        )
        
        self.create_definition(standard_workflow)
        
        # 快速原型工作流
        rapid_workflow = WorkflowDefinition(
            workflow_id="rapid-prototype-workflow",
            name="快速原型工作流",
            description="快速验证想法的简化流程",
            steps=[
                WorkflowStep(
                    step_id="quick-design",
                    name="快速设计",
                    description="快速设计和实现",
                    role_id="developer",
                    action="rapid_implementation",
                    inputs={"approach": "prototype"},
                    outputs={"prototype": None}
                )
            ]
        )
        
        self.create_definition(rapid_workflow)
        
        print(f"✅ 已创建 {len(self.definitions)} 个默认工作流")


def main():
    """示例用法"""
    # 创建工作流引擎
    engine = WorkflowEngine(storage_path=".")
    
    # 创建默认工作流
    engine.create_default_workflows()
    
    # 注册执行器示例
    def mock_executor(step, inputs, instance):
        print(f"  执行动作：{step.action}")
        print(f"  输入：{inputs}")
        return {"status": "success"}
    
    engine.register_executor("analyze_requirements", mock_executor)
    engine.register_executor("design_architecture", mock_executor)
    engine.register_executor("implement_code", mock_executor)
    engine.register_executor("execute_tests", mock_executor)
    engine.register_executor("rapid_implementation", mock_executor)
    
    # 启动工作流
    instance = engine.start_workflow(
        "standard-dev-workflow",
        variables={"detail_level": "high"}
    )
    
    if instance:
        # 查看进度
        progress = engine.get_progress(instance.instance_id)
        print(f"\n📊 进度:")
        for key, value in progress.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

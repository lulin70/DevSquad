#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准化工作流程模块 v1.0

增强现有工作流引擎，提供流程模板库、配置工具、状态可视化和自然语言触发机制。

核心功能:
1. 常见任务流程模板库
2. 流程配置工具，支持通过对话自定义流程
3. 流程执行状态可视化
4. 自然语言触发机制
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

# 导入现有工作流引擎
try:
    from workflow_engine import WorkflowEngine, WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowStatus, StepStatus
    WORKFLOW_AVAILABLE = True
except ImportError:
    WORKFLOW_AVAILABLE = False
    print("⚠️  工作流引擎不可用，将使用简化实现")


class WorkflowTemplateType(Enum):
    """工作流模板类型"""
    STANDARD_DEV = "standard_dev"  # 标准开发流程
    RAPID_PROTOTYPE = "rapid_prototype"  # 快速原型流程
    CODE_ANALYSIS = "code_analysis"  # 代码分析流程
    DOCUMENTATION = "documentation"  # 文档处理流程
    QUALITY_ASSURANCE = "quality_assurance"  # 质量保证流程
    DEPLOYMENT = "deployment"  # 部署流程


@dataclass
class WorkflowTemplate:
    """工作流模板"""
    template_id: str
    type: WorkflowTemplateType
    name: str
    description: str
    steps: List[WorkflowStep]
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowConfiguration:
    """工作流配置"""
    config_id: str
    template_id: str
    name: str
    description: str
    custom_steps: List[WorkflowStep] = field(default_factory=list)
    overrides: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class WorkflowVisualization:
    """工作流可视化信息"""
    instance_id: str
    workflow_id: str
    status: str
    progress: float
    steps: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    estimated_completion: Optional[str] = None


class StandardizedWorkflow:
    """
    标准化工作流程管理（生命周期增强版）
    
    增强现有工作流引擎，提供流程模板库、配置工具、状态可视化和自然语言触发机制。
    集成 PromptRegistry，每个步骤绑定生命周期阶段提示词和门禁检查。
    """

    def __init__(self, storage_path: str = "."):
        self.storage_path = Path(storage_path) / "workflows"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        if WORKFLOW_AVAILABLE:
            self.engine = WorkflowEngine(storage_path=storage_path)
            print("✅ 工作流引擎已初始化")
        else:
            self.engine = None
            print("⚠️  工作流引擎未初始化，使用简化实现")
        
        self.templates: Dict[str, WorkflowTemplate] = {}
        self.configurations: Dict[str, WorkflowConfiguration] = {}
        self.trigger_phrases = self._load_trigger_phrases()
        
        self._prompt_registry = None
        self._init_prompt_registry()
        
        self._load_templates()
        self._load_configurations()

    def _init_prompt_registry(self):
        try:
            project_root = Path(__file__).parent.parent
            sys.path.insert(0, str(project_root))
            from prompts.registry import PromptRegistry
            prompts_dir = project_root / "prompts"
            if prompts_dir.exists():
                self._prompt_registry = PromptRegistry(str(prompts_dir))
                print("✅ PromptRegistry 已集成到工作流")
        except Exception as e:
            print(f"⚠️  PromptRegistry 集成失败：{e}")

    def get_lifecycle_prompt(self, role_id: str, stage_id: str) -> Optional[str]:
        if not self._prompt_registry:
            return None
        try:
            return self._prompt_registry.compose_prompt(role_id, stage_id, include_gate=True)
        except Exception:
            return None

    def get_stage_gate_checklist(self, stage_id: str) -> List[str]:
        if not self._prompt_registry:
            return []
        try:
            stage_info = self._prompt_registry.get_stage_prompt(stage_id)
            if stage_info:
                return stage_info.exit_conditions
        except Exception:
            pass
        return []

    def _load_trigger_phrases(self) -> Dict[str, List[str]]:
        """
        加载自然语言触发短语
        
        Returns:
            Dict[str, List[str]]: 触发短语映射
        """
        return {
            "start_workflow": [
                r'开始工作流', r'启动流程', r'运行工作流',
                r'start workflow', r'run workflow', r'execute process'
            ],
            "pause_workflow": [
                r'暂停工作流', r'停止流程', r'暂停执行',
                r'pause workflow', r'stop process', r'hold execution'
            ],
            "resume_workflow": [
                r'恢复工作流', r'继续流程', r'重新开始',
                r'resume workflow', r'continue process', r'restart execution'
            ],
            "check_progress": [
                r'查看进度', r'工作流状态', r'流程进展',
                r'check progress', r'workflow status', r'process progress'
            ],
            "create_workflow": [
                r'创建工作流', r'新建流程', r'配置工作流',
                r'create workflow', r'new process', r'configure workflow'
            ]
        }

    def _load_templates(self):
        """加载工作流模板"""
        # 标准开发流程（8阶段全生命周期）
        standard_dev_template = WorkflowTemplate(
            template_id="standard_dev",
            type=WorkflowTemplateType.STANDARD_DEV,
            name="标准开发流程（8阶段全生命周期）",
            description="需求→架构→UI→测试设计→任务分解→开发→测试验证→发布评审",
            steps=[
                WorkflowStep(
                    step_id="stage1_requirements",
                    name="阶段1：需求分析",
                    description="分析需求，编写PRD，定义验收标准",
                    role_id="product-manager",
                    action="execute_stage1",
                    inputs={"detail_level": "high"},
                    outputs={"prd": None}
                ),
                WorkflowStep(
                    step_id="stage2_architecture",
                    name="阶段2：架构设计",
                    description="设计系统架构，定义接口和数据模型",
                    role_id="architect",
                    action="execute_stage2",
                    inputs={"requirements": "${prd}"},
                    outputs={"architecture": None}
                ),
                WorkflowStep(
                    step_id="stage3_ui_design",
                    name="阶段3：UI设计",
                    description="设计界面和交互流程",
                    role_id="ui-designer",
                    action="execute_stage3",
                    inputs={"architecture": "${architecture}"},
                    outputs={"ui_design": None}
                ),
                WorkflowStep(
                    step_id="stage4_test_design",
                    name="阶段4：测试设计",
                    description="设计测试策略和用例，定义质量门禁",
                    role_id="tester",
                    action="execute_stage4",
                    inputs={"architecture": "${architecture}", "ui_design": "${ui_design}"},
                    outputs={"test_plan": None}
                ),
                WorkflowStep(
                    step_id="stage5_task_breakdown",
                    name="阶段5：任务分解",
                    description="分解开发任务，制定开发计划",
                    role_id="solo-coder",
                    action="execute_stage5",
                    inputs={"architecture": "${architecture}", "test_plan": "${test_plan}"},
                    outputs={"task_list": None}
                ),
                WorkflowStep(
                    step_id="stage6_development",
                    name="阶段6：开发实现",
                    description="实现功能代码，编写单元测试",
                    role_id="solo-coder",
                    action="execute_stage6",
                    inputs={"task_list": "${task_list}"},
                    outputs={"code": None}
                ),
                WorkflowStep(
                    step_id="stage7_test_verify",
                    name="阶段7：测试验证",
                    description="执行集成测试、性能测试、安全测试",
                    role_id="tester",
                    action="execute_stage7",
                    inputs={"code": "${code}"},
                    outputs={"test_report": None}
                ),
                WorkflowStep(
                    step_id="stage8_release_review",
                    name="阶段8：发布评审",
                    description="架构合规性审查、业务验收、发布决策",
                    role_id="architect",
                    action="execute_stage8",
                    inputs={"test_report": "${test_report}"},
                    outputs={"release_decision": None}
                )
            ]
        )
        
        # 快速原型流程
        rapid_prototype_template = WorkflowTemplate(
            template_id="rapid_prototype",
            type=WorkflowTemplateType.RAPID_PROTOTYPE,
            name="快速原型流程",
            description="快速验证想法的简化流程",
            steps=[
                WorkflowStep(
                    step_id="quick_design",
                    name="快速设计",
                    description="快速设计和实现",
                    role_id="solo-coder",
                    action="rapid_implementation",
                    inputs={"approach": "prototype"},
                    outputs={"prototype": None}
                )
            ]
        )
        
        # 代码分析流程
        code_analysis_template = WorkflowTemplate(
            template_id="code_analysis",
            type=WorkflowTemplateType.CODE_ANALYSIS,
            name="代码分析流程",
            description="代码质量分析和改进流程",
            steps=[
                WorkflowStep(
                    step_id="code_scan",
                    name="代码扫描",
                    description="扫描代码质量问题",
                    role_id="solo-coder",
                    action="scan_code",
                    inputs={"depth": "deep"},
                    outputs={"scan_results": None}
                ),
                WorkflowStep(
                    step_id="quality_analysis",
                    name="质量分析",
                    description="分析代码质量问题",
                    role_id="tester",
                    action="analyze_quality",
                    inputs={"results": "${scan_results}"},
                    outputs={"quality_report": None}
                ),
                WorkflowStep(
                    step_id="improvement",
                    name="代码改进",
                    description="根据分析结果改进代码",
                    role_id="solo-coder",
                    action="improve_code",
                    inputs={"report": "${quality_report}"},
                    outputs={"improved_code": None}
                )
            ]
        )
        
        # 文档处理流程
        documentation_template = WorkflowTemplate(
            template_id="documentation",
            type=WorkflowTemplateType.DOCUMENTATION,
            name="文档处理流程",
            description="文档生成和验证流程",
            steps=[
                WorkflowStep(
                    step_id="doc_generation",
                    name="文档生成",
                    description="生成项目文档",
                    role_id="product-manager",
                    action="generate_documentation",
                    inputs={"format": "markdown"},
                    outputs={"documentation": None}
                ),
                WorkflowStep(
                    step_id="doc_validation",
                    name="文档验证",
                    description="验证文档质量",
                    role_id="product-manager",
                    action="validate_documentation",
                    inputs={"docs": "${documentation}"},
                    outputs={"validation_result": None}
                )
            ]
        )
        
        # 质量保证流程
        quality_assurance_template = WorkflowTemplate(
            template_id="quality_assurance",
            type=WorkflowTemplateType.QUALITY_ASSURANCE,
            name="质量保证流程",
            description="全面质量检查流程",
            steps=[
                WorkflowStep(
                    step_id="code_quality",
                    name="代码质量检查",
                    description="检查代码质量",
                    role_id="tester",
                    action="check_code_quality",
                    inputs={"level": "comprehensive"},
                    outputs={"code_quality_result": None}
                ),
                WorkflowStep(
                    step_id="security_check",
                    name="安全检查",
                    description="检查安全漏洞",
                    role_id="tester",
                    action="check_security",
                    inputs={"scope": "full"},
                    outputs={"security_result": None}
                ),
                WorkflowStep(
                    step_id="performance_test",
                    name="性能测试",
                    description="测试系统性能",
                    role_id="tester",
                    action="test_performance",
                    inputs={"load": "high"},
                    outputs={"performance_result": None}
                )
            ]
        )
        
        # 部署流程
        deployment_template = WorkflowTemplate(
            template_id="deployment",
            type=WorkflowTemplateType.DEPLOYMENT,
            name="部署流程",
            description="系统部署和上线流程",
            steps=[
                WorkflowStep(
                    step_id="build",
                    name="构建系统",
                    description="构建部署包",
                    role_id="solo-coder",
                    action="build_system",
                    inputs={"environment": "production"},
                    outputs={"build_result": None}
                ),
                WorkflowStep(
                    step_id="deploy",
                    name="部署系统",
                    description="部署到目标环境",
                    role_id="solo-coder",
                    action="deploy_system",
                    inputs={"build": "${build_result}"},
                    outputs={"deploy_result": None}
                ),
                WorkflowStep(
                    step_id="validation",
                    name="部署验证",
                    description="验证部署结果",
                    role_id="tester",
                    action="validate_deployment",
                    inputs={"deploy_result": "${deploy_result}"},
                    outputs={"validation_result": None}
                )
            ]
        )
        
        # 注册模板
        self.templates["standard_dev"] = standard_dev_template
        self.templates["rapid_prototype"] = rapid_prototype_template
        self.templates["code_analysis"] = code_analysis_template
        self.templates["documentation"] = documentation_template
        self.templates["quality_assurance"] = quality_assurance_template
        self.templates["deployment"] = deployment_template
        
        print(f"✅ 已加载 {len(self.templates)} 个工作流模板")

    def _load_configurations(self):
        """加载工作流配置"""
        configs_file = self.storage_path / "configurations.json"
        if configs_file.exists():
            try:
                with open(configs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for config_id, config_data in data.get('configurations', {}).items():
                    # 恢复配置
                    custom_steps = []
                    for step_data in config_data.get('custom_steps', []):
                        step = WorkflowStep(
                            step_id=step_data['step_id'],
                            name=step_data['name'],
                            description=step_data['description'],
                            role_id=step_data['role_id'],
                            action=step_data['action'],
                            inputs=step_data.get('inputs', {}),
                            outputs=step_data.get('outputs', {})
                        )
                        custom_steps.append(step)
                    
                    config = WorkflowConfiguration(
                        config_id=config_data['config_id'],
                        template_id=config_data['template_id'],
                        name=config_data['name'],
                        description=config_data['description'],
                        custom_steps=custom_steps,
                        overrides=config_data.get('overrides', {})
                    )
                    self.configurations[config_id] = config
                
                print(f"✅ 已加载 {len(self.configurations)} 个工作流配置")
                
            except Exception as e:
                print(f"加载工作流配置失败：{e}")

    def _save_configurations(self):
        """保存工作流配置"""
        configs_file = self.storage_path / "configurations.json"
        
        data = {
            'version': '1.0',
            'updated_at': datetime.now().isoformat(),
            'configurations': {}
        }
        
        for config_id, config in self.configurations.items():
            config_dict = {
                'config_id': config.config_id,
                'template_id': config.template_id,
                'name': config.name,
                'description': config.description,
                'custom_steps': [{
                    'step_id': step.step_id,
                    'name': step.name,
                    'description': step.description,
                    'role_id': step.role_id,
                    'action': step.action,
                    'inputs': step.inputs,
                    'outputs': step.outputs
                } for step in config.custom_steps],
                'overrides': config.overrides,
                'created_at': config.created_at
            }
            data['configurations'][config_id] = config_dict
        
        try:
            with open(configs_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存工作流配置失败：{e}")

    def get_templates(self) -> List[WorkflowTemplate]:
        """
        获取所有工作流模板
        
        Returns:
            List[WorkflowTemplate]: 模板列表
        """
        return list(self.templates.values())

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """
        获取指定模板
        
        Args:
            template_id: 模板 ID
            
        Returns:
            Optional[WorkflowTemplate]: 模板
        """
        return self.templates.get(template_id)

    def create_workflow_from_template(self, template_id: str, 
                                    name: str, 
                                    description: str, 
                                    overrides: Dict[str, Any] = None) -> Optional[WorkflowDefinition]:
        """
        从模板创建工作流
        
        Args:
            template_id: 模板 ID
            name: 工作流名称
            description: 工作流描述
            overrides: 覆盖参数
            
        Returns:
            Optional[WorkflowDefinition]: 工作流定义
        """
        template = self.templates.get(template_id)
        if not template:
            print(f"❌ 模板不存在：{template_id}")
            return None
        
        # 创建工作流定义
        workflow_id = f"{template_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        steps = []
        
        # 复制模板步骤
        for step in template.steps:
            new_step = WorkflowStep(
                step_id=step.step_id,
                name=step.name,
                description=step.description,
                role_id=step.role_id,
                action=step.action,
                inputs=step.inputs.copy(),
                outputs=step.outputs.copy()
            )
            steps.append(new_step)
        
        # 应用覆盖
        if overrides:
            for step in steps:
                if step.step_id in overrides:
                    step.inputs.update(overrides[step.step_id])
        
        definition = WorkflowDefinition(
            workflow_id=workflow_id,
            name=name,
            description=description,
            steps=steps,
            variables=template.variables.copy()
        )
        
        # 保存到工作流引擎
        if self.engine:
            self.engine.create_definition(definition)
        
        print(f"✅ 从模板创建工作流：{name}")
        return definition

    def create_configuration(self, template_id: str, 
                           name: str, 
                           description: str, 
                           custom_steps: List[WorkflowStep] = None, 
                           overrides: Dict[str, Any] = None) -> WorkflowConfiguration:
        """
        创建工作流配置
        
        Args:
            template_id: 模板 ID
            name: 配置名称
            description: 配置描述
            custom_steps: 自定义步骤
            overrides: 覆盖参数
            
        Returns:
            WorkflowConfiguration: 配置
        """
        config_id = f"config-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        config = WorkflowConfiguration(
            config_id=config_id,
            template_id=template_id,
            name=name,
            description=description,
            custom_steps=custom_steps or [],
            overrides=overrides or {}
        )
        
        self.configurations[config_id] = config
        self._save_configurations()
        
        print(f"✅ 创建工作流配置：{name}")
        return config

    def get_configurations(self) -> List[WorkflowConfiguration]:
        """
        获取所有配置
        
        Returns:
            List[WorkflowConfiguration]: 配置列表
        """
        return list(self.configurations.values())

    def get_configuration(self, config_id: str) -> Optional[WorkflowConfiguration]:
        """
        获取指定配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            Optional[WorkflowConfiguration]: 配置
        """
        return self.configurations.get(config_id)

    def start_workflow_from_config(self, config_id: str, 
                                 variables: Dict[str, Any] = None) -> Optional[WorkflowInstance]:
        """
        从配置启动工作流
        
        Args:
            config_id: 配置 ID
            variables: 初始变量
            
        Returns:
            Optional[WorkflowInstance]: 工作流实例
        """
        config = self.configurations.get(config_id)
        if not config:
            print(f"❌ 配置不存在：{config_id}")
            return None
        
        # 从模板创建工作流
        definition = self.create_workflow_from_template(
            template_id=config.template_id,
            name=config.name,
            description=config.description,
            overrides=config.overrides
        )
        
        if not definition:
            return None
        
        # 启动工作流
        if self.engine:
            instance = self.engine.start_workflow(
                definition.workflow_id,
                variables=variables
            )
            print(f"✅ 从配置启动工作流：{config.name}")
            return instance
        
        return None

    def visualize_workflow(self, instance_id: str) -> Optional[WorkflowVisualization]:
        """
        可视化工作流状态
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            Optional[WorkflowVisualization]: 可视化信息
        """
        if not self.engine:
            return None
        
        instance = self.engine.get_instance(instance_id)
        if not instance:
            return None
        
        # 获取进度信息
        progress_info = self.engine.get_progress(instance_id)
        
        # 构建步骤信息
        definition = self.engine.get_definition(instance.workflow_id)
        steps_info = []
        if definition:
            for step in definition.steps:
                step_info = {
                    'step_id': step.step_id,
                    'name': step.name,
                    'status': step.status.value,
                    'description': step.description,
                    'role_id': step.role_id
                }
                steps_info.append(step_info)
        
        # 构建时间线
        timeline = [
            {
                'event': 'workflow_started',
                'timestamp': instance.started_at,
                'description': '工作流开始'
            }
        ]
        
        # 添加步骤事件
        if definition:
            for step in definition.steps:
                if step.started_at:
                    timeline.append({
                        'event': 'step_started',
                        'step_id': step.step_id,
                        'timestamp': step.started_at,
                        'description': f"步骤开始: {step.name}"
                    })
                if step.completed_at:
                    timeline.append({
                        'event': 'step_completed',
                        'step_id': step.step_id,
                        'timestamp': step.completed_at,
                        'description': f"步骤完成: {step.name}"
                    })
        
        if instance.completed_at:
            timeline.append({
                'event': 'workflow_completed',
                'timestamp': instance.completed_at,
                'description': '工作流完成'
            })
        
        # 估算完成时间
        estimated_completion = None
        if instance.status == WorkflowStatus.RUNNING:
            # 简单估算：基于已完成步骤和总步骤
            if progress_info.get('total_steps', 0) > 0:
                elapsed = (datetime.now() - datetime.fromisoformat(instance.started_at)).total_seconds()
                progress = progress_info.get('progress', 0)
                if progress > 0:
                    total_estimated = elapsed / progress
                    remaining = total_estimated - elapsed
                    estimated_completion = (datetime.now() + timedelta(seconds=remaining)).isoformat()
        
        visualization = WorkflowVisualization(
            instance_id=instance_id,
            workflow_id=instance.workflow_id,
            status=instance.status.value,
            progress=progress_info.get('progress', 0),
            steps=steps_info,
            timeline=timeline,
            estimated_completion=estimated_completion
        )
        
        return visualization

    def detect_trigger(self, message: str) -> Optional[Dict[str, Any]]:
        """
        检测自然语言触发
        
        Args:
            message: 用户消息
            
        Returns:
            Optional[Dict[str, Any]]: 触发信息
        """
        message_lower = message.lower()
        
        for action, phrases in self.trigger_phrases.items():
            for phrase in phrases:
                if re.search(phrase, message_lower):
                    # 提取工作流名称或配置
                    workflow_name = self._extract_workflow_name(message)
                    config_name = self._extract_config_name(message)
                    
                    return {
                        'action': action,
                        'workflow_name': workflow_name,
                        'config_name': config_name,
                        'message': message
                    }
        
        return None

    def _extract_workflow_name(self, message: str) -> Optional[str]:
        """
        提取工作流名称
        
        Args:
            message: 用户消息
            
        Returns:
            Optional[str]: 工作流名称
        """
        # 简单的名称提取逻辑
        patterns = [
            r'工作流\s*(.+?)\s*启动',
            r'启动\s*(.+?)\s*工作流',
            r'流程\s*(.+?)\s*启动',
            r'启动\s*(.+?)\s*流程'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1).strip()
        
        return None

    def _extract_config_name(self, message: str) -> Optional[str]:
        """
        提取配置名称
        
        Args:
            message: 用户消息
            
        Returns:
            Optional[str]: 配置名称
        """
        patterns = [
            r'配置\s*(.+?)\s*启动',
            r'启动\s*(.+?)\s*配置'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1).strip()
        
        return None

    def handle_natural_language(self, message: str) -> Dict[str, Any]:
        """
        处理自然语言指令
        
        Args:
            message: 用户消息
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 检测触发
        trigger = self.detect_trigger(message)
        if not trigger:
            return {
                'action': 'none',
                'message': '未检测到工作流相关指令'
            }
        
        action = trigger['action']
        result = {'action': action}
        
        if action == 'start_workflow':
            # 启动工作流
            workflow_name = trigger.get('workflow_name')
            if workflow_name:
                # 查找匹配的模板
                for template in self.templates.values():
                    if template.name == workflow_name:
                        # 创建并启动工作流
                        definition = self.create_workflow_from_template(
                            template_id=template.template_id,
                            name=workflow_name,
                            description=f"从模板创建的工作流: {workflow_name}"
                        )
                        if definition and self.engine:
                            instance = self.engine.start_workflow(definition.workflow_id)
                            result['workflow'] = workflow_name
                            result['instance_id'] = instance.instance_id if instance else None
                            result['message'] = f"已启动工作流: {workflow_name}"
                        break
            else:
                result['message'] = '请指定要启动的工作流名称'
        
        elif action == 'pause_workflow':
            # 暂停工作流
            # 简化处理，实际需要更复杂的逻辑
            result['message'] = '工作流暂停功能已触发'
        
        elif action == 'resume_workflow':
            # 恢复工作流
            result['message'] = '工作流恢复功能已触发'
        
        elif action == 'check_progress':
            # 检查进度
            # 简化处理，实际需要更复杂的逻辑
            result['message'] = '工作流进度检查功能已触发'
        
        elif action == 'create_workflow':
            # 创建工作流
            result['message'] = '工作流创建功能已触发'
        
        return result

    def register_executor(self, action: str, executor: Callable):
        """
        注册步骤执行器
        
        Args:
            action: 动作名称
            executor: 执行函数
        """
        if self.engine:
            self.engine.register_executor(action, executor)


# 导入 timedelta
from datetime import timedelta


def main():
    """示例用法"""
    # 创建标准化工作流程
    workflow = StandardizedWorkflow(storage_path=".")
    
    # 查看模板
    print("=" * 80)
    print("工作流模板列表")
    print("=" * 80)
    for template in workflow.get_templates():
        print(f"\n模板 ID: {template.template_id}")
        print(f"名称: {template.name}")
        print(f"描述: {template.description}")
        print(f"步骤数: {len(template.steps)}")
    
    # 创建配置
    print("\n" + "=" * 80)
    print("创建工作流配置")
    print("=" * 80)
    config = workflow.create_configuration(
        template_id="standard_dev",
        name="我的开发流程",
        description="自定义的开发流程配置",
        overrides={
            "prd": {"detail_level": "medium"},
            "development": {"approach": "agile"}
        }
    )
    
    # 从配置启动工作流
    print("\n" + "=" * 80)
    print("从配置启动工作流")
    print("=" * 80)
    instance = workflow.start_workflow_from_config(
        config_id=config.config_id,
        variables={"project_name": "Test Project"}
    )
    
    if instance:
        # 查看进度
        print(f"\n工作流实例 ID: {instance.instance_id}")
        print(f"状态: {instance.status.value}")
        
        # 可视化工作流
        visualization = workflow.visualize_workflow(instance.instance_id)
        if visualization:
            print(f"\n工作流可视化:")
            print(f"  进度: {visualization.progress:.2%}")
            print(f"  状态: {visualization.status}")
            print(f"  步骤数: {len(visualization.steps)}")
    
    # 测试自然语言触发
    print("\n" + "=" * 80)
    print("测试自然语言触发")
    print("=" * 80)
    test_messages = [
        "请启动标准开发流程",
        "开始我的开发流程",
        "查看工作流进度",
        "暂停当前工作流"
    ]
    
    for message in test_messages:
        print(f"\n用户消息: {message}")
        result = workflow.handle_natural_language(message)
        print(f"处理结果: {result}")


if __name__ == "__main__":
    main()

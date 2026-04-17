#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding 模块

集成 Vibe Coding 核心理念和功能到 MultiAgentSkill
"""

from .planning_engine import PlanningEngine
from .prompt_evolution import PromptEvolutionSystem
from .enhanced_context_manager import EnhancedDualLayerContextManager, ModelCoordinator, ModelType, ModelCapability, ModelInfo, ModelAssignment
from .module_manager import ModuleManager, ModuleType as MM_ModuleType, ModuleStatus, ModuleDependency, ModuleInterface, Module, ModuleConfig
from .multimodal_processor import MultimodalProcessor, ImageProcessor, AudioProcessor, TextToCodeProcessor, ModalityType, ImageFormat, AudioFormat, ImageData, AudioData, ImageRecognitionResult, SpeechRecognitionResult, TextToCodeResult

__all__ = ['PlanningEngine', 'PromptEvolutionSystem', 'EnhancedDualLayerContextManager', 'ModelCoordinator', 'ModelType', 'ModelCapability', 'ModelInfo', 'ModelAssignment', 'ModuleManager', 'MM_ModuleType', 'ModuleStatus', 'ModuleDependency', 'ModuleInterface', 'Module', 'ModuleConfig', 'MultimodalProcessor', 'ImageProcessor', 'AudioProcessor', 'TextToCodeProcessor', 'ModalityType', 'ImageFormat', 'AudioFormat', 'ImageData', 'AudioData', 'ImageRecognitionResult', 'SpeechRecognitionResult', 'TextToCodeResult']
__version__ = '1.0.0'

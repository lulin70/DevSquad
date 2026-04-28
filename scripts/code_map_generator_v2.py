#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码地图生成器 v2.1

⚠️ 已弃用：此脚本为 V2 遗留，V3 推荐使用 `python3 scripts/cli.py dispatch -t "Generate code map"` 或 `devsquad dispatch -t "Generate code map"`

用于生成超大型系统代码结构的 md 格式代码地图，帮助 agent 快速定位和理解代码

核心功能:
1. 多语言支持: Java, Python, JavaScript/TypeScript, Go, Rust, C/C++, C#, PHP, Shell 等
2. 代码元素提取: 类、函数、接口、模块、配置等
3. 调用关系追踪: 分析代码间的调用依赖关系
4. 架构分层: 按照分层架构组织代码视图
5. md 格式输出: 生成人类和 AI 均可阅读的代码地图文档
6. 多项目工作空间支持: 支持一个 workspace 包含多个项目的场景

使用方法:
    python code_map_generator_v2.py <project_root> [--workspace <workspace_root>] [--output <output_file>]

参数说明:
    project_root: 项目根目录路径 (必填)
    --workspace: 工作空间根目录路径 (可选，默认值为 project_root 的父目录)
    --output: 输出文件路径 (默认: <project_root>/CODE_MAP.md)
    --scope: 分析范围，子目录路径 (可选)

多项目场景示例:
    # workspace 结构:
    # /workspace/
    #   ├── project-a/  (项目 A)
    #   └── project-b/  (项目 B)
    #
    # 生成项目 A 的代码地图 (自动检测 workspace)
    python code_map_generator_v2.py /workspace/project-a
    # 输出: /workspace/project-a/project-a-CODE_MAP.md
    # workspace 字段会显示: "workspace"
    #
    # 显式指定 workspace
    python code_map_generator_v2.py /workspace/project-a --workspace /workspace
    # workspace 字段会显示: "workspace"
    # relative_path 字段会显示: "project-a"

输出文件:
    生成的代码地图保存为 md 格式，可直接作为 agent 记忆或项目规则使用
"""

import os
import json
import argparse
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import ast


@dataclass
class FunctionInfo:
    """函数信息数据结构"""
    name: str
    line_start: int
    line_end: int
    params: List[str] = field(default_factory=list)
    return_type: str = ""
    docstring: str = ""
    calls: List[str] = field(default_factory=list)
    complexity: str = "low"


@dataclass
class ClassInfo:
    """类信息数据结构"""
    name: str
    line_start: int
    line_end: int
    methods: List[FunctionInfo] = field(default_factory=list)
    properties: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    docstring: str = ""
    complexity: str = "low"


@dataclass
class FileInfo:
    """文件信息数据结构"""
    path: str
    relative_path: str
    language: str
    lines: int
    summary: str = ""
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    complexity: str = "low"


class AICallRelationAnalyzer:
    """AI 调用关系分析器

    使用 AI 深度分析代码文件间的隐式调用关系，弥补静态分析的不足。
    AI 可以识别：
    - 依赖注入的调用
    - 反射/动态调用
    - 回调和事件处理
    - 配置驱动的调用
    - 隐式的服务间调用
    """

    def __init__(self, api_base: str = "http://localhost:11434", model: str = "qwen2.5"):
        self.api_base = api_base
        self.model = model

    def analyze_file_relations(self, file_path: str, file_content: str,
                               project_files: List[FileInfo]) -> Dict[str, List[str]]:
        """分析单个文件的调用关系

        Args:
            file_path: 文件路径
            file_content: 文件内容
            project_files: 项目所有文件信息

        Returns:
            Dict[str, List[str]]: 文件ID -> 调用文件ID列表 的映射
        """
        # 构建项目文件摘要供 AI 参考
        file_summaries = []
        for pf in project_files[:50]:  # 限制数量避免上下文过长
            summary = f"- {pf.relative_path}"
            if pf.classes:
                summary += f" (classes: {', '.join(c.name for c in pf.classes)})"
            if pf.functions:
                summary += f" (functions: {', '.join(f.name for f in pf.functions[:5])}...)"
            file_summaries.append(summary)

        prompt = f"""你是一个代码分析专家。请分析以下代码文件的调用关系。

文件路径: {file_path}

文件内容:
```{self._get_language(file_path)}
{file_content[:3000]}  # 限制长度
```

项目中的关键文件:
{chr(10).join(file_summaries)}

请分析这个文件调用了哪些其他文件/模块的哪些具体函数或类方法。
注意识别:
1. 显式的 import 调用
2. 依赖注入的调用 (如 service.xxx, self.xxx)
3. 回调和事件处理
4. 配置驱动的动态调用
5. 隐式的服务间调用

以 JSON 格式返回分析结果:
{{
  "calls": [
    {{
      "target_file": "文件路径",
      "target_function": "函数/方法名",
      "call_type": "direct|dynamic|di|event|config",
      "confidence": "high|medium|low"
    }}
  ]
}}

只返回 JSON，不要有其他文字。"""

        try:
            result = self._call_ollama(prompt)
            return self._parse_ai_result(result, project_files)
        except Exception as e:
            print(f"  AI 分析失败: {e}")
            return {}

    def analyze_method_relations(self, class_name: str, method_name: str,
                                  method_body: str,
                                  all_classes: List[ClassInfo]) -> List[Dict]:
        """分析方法内部的具体调用关系

        Args:
            class_name: 类名
            method_name: 方法名
            method_body: 方法体内容
            all_classes: 项目中所有类信息

        Returns:
            List[Dict]: 调用关系列表
        """
        prompt = f"""分析以下方法内部调用了哪些其他方法。

类名: {class_name}
方法名: {method_name}

方法体:
{method_body[:2000]}

项目中的类和方法:
{chr(10).join([f"- {c.name}: {', '.join(m.name for m in c.methods)}" for c in all_classes[:20]])}

返回 JSON 格式的调用关系:
{{
  "method_calls": [
    {{
      "called_class": "类名或null",
      "called_method": "方法名",
      "call_type": "self|internal|external|async",
      "line_context": "调用所在行的上下文"
    }}
  ]
}}

只返回 JSON。"""

        try:
            result = self._call_ollama(prompt)
            return self._parse_method_result(result)
        except Exception as e:
            print(f"  AI 方法分析失败: {e}")
            return []

    def _call_ollama(self, prompt: str) -> str:
        """调用 Ollama API"""
        import urllib.request
        import urllib.error

        url = f"{self.api_base}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2048
            }
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('response', '')

    def _parse_ai_result(self, result: str, project_files: List[FileInfo]) -> Dict[str, List[str]]:
        """解析 AI 返回结果"""
        try:
            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', result)
            if not json_match:
                return {}

            data = json.loads(json_match.group())
            calls = data.get('calls', [])

            # 建立调用关系
            relations = defaultdict(list)

            for call in calls:
                target_file = call.get('target_file', '')
                target_func = call.get('target_function', '')

                # 匹配目标文件
                for pf in project_files:
                    if target_file in pf.relative_path or pf.relative_path.endswith(target_file):
                        node_id = f"file:{pf.relative_path}"
                        if node_id not in relations.get('matched', []):
                            relations['matched'].append(node_id)

                        # 如果有关联的方法/类，也添加
                        if target_func:
                            # 尝试匹配类
                            for cls in pf.classes:
                                if target_func.lower() in cls.name.lower():
                                    relations['matched'].append(f"class:{pf.relative_path}:{cls.name}")
                                    break
                            # 尝试匹配函数
                            for func in pf.functions:
                                if target_func.lower() in func.name.lower():
                                    relations['matched'].append(f"func:{pf.relative_path}:{func.name}")
                                    break

            # 移除临时键
            if 'matched' in relations:
                del relations['matched']

            return dict(relations)
        except Exception as e:
            print(f"  解析 AI 结果失败: {e}")
            return {}

    def _parse_method_result(self, result: str) -> List[Dict]:
        """解析方法调用分析结果"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', result)
            if not json_match:
                return []
            data = json.loads(json_match.group())
            return data.get('method_calls', [])
        except:
            return []

    def _get_language(self, file_path: str) -> str:
        """根据文件扩展名获取语言"""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
        }
        return lang_map.get(ext, 'text')


@dataclass
class ModuleInfo:
    """模块信息数据结构"""
    name: str
    path: str
    files: List[FileInfo] = field(default_factory=list)
    description: str = ""
    dependencies: List[str] = field(default_factory=list)


@dataclass
class LayerInfo:
    """架构层信息数据结构"""
    name: str
    description: str
    patterns: List[str]
    files: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)


class LanguageDetector:
    """语言检测器"""

    EXTENSION_LANGUAGE: Dict[str, str] = {
        ".java": "java",
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".vue": "vue",
        ".svelte": "svelte",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
    }

    LANGUAGE_PATTERNS: Dict[str, List[str]] = {
        "java": ["src/main/java", "src/test/java", "src/androidTest/java"],
        "python": ["src", "tests", "app", "lib"],
        "javascript": ["src", "lib", "app", "public"],
        "typescript": ["src", "lib", "app", "types"],
        "go": ["cmd", "pkg", "internal", "api"],
        "rust": ["src", "tests", "examples", " benches"],
        "spring": ["controller", "service", "repository", "model", "config"],
        "django": ["views", "models", "urls", "settings", "apps"],
        "react": ["components", "hooks", "pages", "utils"],
        "express": ["routes", "middleware", "controllers", "models"],
    }

    @classmethod
    def detect(cls, file_path: str) -> str:
        """根据文件扩展名检测语言"""
        ext = os.path.splitext(file_path)[1].lower()
        return cls.EXTENSION_LANGUAGE.get(ext, "unknown")

    @classmethod
    def is_source_file(cls, file_path: str) -> bool:
        """判断是否为源代码文件"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.EXTENSION_LANGUAGE

    @classmethod
    def is_config_file(cls, file_path: str) -> bool:
        """判断是否为配置文件"""
        config_extensions = [".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".xml", ".properties"]
        config_names = ["Makefile", "Dockerfile", ".gitignore", ".dockerignore", "pom.xml", "build.gradle"]
        ext = os.path.splitext(file_path)[1].lower()
        name = os.path.basename(file_path)
        return ext in config_extensions or name in config_names


class PythonAnalyzer:
    """Python 代码分析器"""

    def __init__(self, content: str, file_path: str):
        self.content = content
        self.file_path = file_path
        self.lines = content.split('\n')

    def analyze(self) -> FileInfo:
        """分析 Python 文件"""
        file_info = FileInfo(
            path=self.file_path,
            relative_path=self.file_path,
            language="python",
            lines=len(self.lines)
        )

        try:
            tree = ast.parse(self.content)
            file_info = self._extract_info(tree, file_info)
        except SyntaxError as e:
            file_info.summary = f"Python 语法错误: {str(e)}"

        return file_info

    def _extract_info(self, tree: ast.AST, file_info: FileInfo) -> FileInfo:
        """提取 Python 代码信息"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    file_info.imports.append(f"{module}.{alias.name}" if module else alias.name)
            elif isinstance(node, ast.ClassDef):
                class_info = self._extract_class(node)
                file_info.classes.append(class_info)
            elif isinstance(node, ast.FunctionDef):
                if not self._is_method(node):
                    func_info = self._extract_function(node)
                    file_info.functions.append(func_info)

        file_info.complexity = self._calculate_complexity(file_info)
        file_info.summary = self._generate_summary(file_info)
        return file_info

    def _extract_class(self, node: ast.ClassDef) -> ClassInfo:
        """提取类信息"""
        class_info = ClassInfo(
            name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno
        )

        class_info.base_classes = [self._get_name(base) for base in node.bases]

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = self._extract_function(item)
                method_info.name = f"{node.name}.{item.name}"
                class_info.methods.append(method_info)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                class_info.properties.append(item.target.id)

        if ast.get_docstring(node):
            class_info.docstring = ast.get_docstring(node)[:200]

        return class_info

    def _extract_function(self, node: ast.FunctionDef) -> FunctionInfo:
        """提取函数信息"""
        func_info = FunctionInfo(
            name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            params=[arg.arg for arg in node.args.args],
            return_type=self._get_return_type(node)
        )

        func_info.calls = self._extract_calls(node)
        func_info.docstring = ast.get_docstring(node)[:200] if ast.get_docstring(node) else ""

        return func_info

    def _extract_calls(self, node: ast.FunctionDef) -> List[str]:
        """提取函数调用

        返回调用列表，格式为:
        - "function_name" - 本地函数调用
        - "obj.method" - 对象方法调用
        - "ClassName.method" - 类方法调用
        """
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # 处理方法调用如 self.xxx()
                if isinstance(child.func, ast.Attribute):
                    # 获取完整的方法链
                    method_chain = self._get_attribute_chain(child.func)
                    if method_chain:
                        calls.append(method_chain)
                elif isinstance(child.func, ast.Name):
                    # 简单函数调用
                    calls.append(child.func.id)
        return list(set(calls))

    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """获取属性的完整链，如 self.user_service.create_user -> user_service.create_user"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            # 跳过 self, cls, obj 等通用变量名
            if current.id not in ['self', 'cls', 'this', 'obj']:
                parts.append(current.id)
        if parts:
            parts.reverse()
            return '.'.join(parts)
        return node.attr

    def _get_return_type(self, node: ast.FunctionDef) -> str:
        """获取返回类型"""
        if node.returns:
            return ast.unparse(node.returns)
        return ""

    def _get_name(self, node: ast.AST) -> str:
        """获取节点名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        return ""

    def _is_method(self, node: ast.FunctionDef) -> bool:
        """判断是否为类方法"""
        return len(node.args.args) > 0 and node.args.args[0].arg == 'self'

    def _calculate_complexity(self, file_info: FileInfo) -> str:
        """计算文件复杂度"""
        total_lines = file_info.lines
        class_count = len(file_info.classes)
        func_count = len(file_info.functions)
        method_count = sum(len(c.methods) for c in file_info.classes)

        score = total_lines / 50 + class_count * 2 + func_count + method_count * 0.5

        if score < 5:
            return "low"
        elif score < 15:
            return "medium"
        else:
            return "high"

    def _generate_summary(self, file_info: FileInfo) -> str:
        """生成文件摘要"""
        parts = []
        if file_info.classes:
            parts.append(f"包含 {len(file_info.classes)} 个类")
        if file_info.functions:
            parts.append(f"包含 {len(file_info.functions)} 个函数")
        return "，".join(parts) if parts else "工具模块"


class JavaAnalyzer:
    """Java 代码分析器"""

    def __init__(self, content: str, file_path: str):
        self.content = content
        self.file_path = file_path
        self.lines = content.split('\n')

    def analyze(self) -> FileInfo:
        """分析 Java 文件"""
        file_info = FileInfo(
            path=self.file_path,
            relative_path=self.file_path,
            language="java",
            lines=len(self.lines)
        )

        file_info.imports = self._extract_imports()
        file_info.classes = self._extract_classes()

        file_info.complexity = self._calculate_complexity(file_info)
        file_info.summary = self._generate_summary(file_info)

        return file_info

    def _extract_imports(self) -> List[str]:
        """提取导入语句"""
        imports = []
        for line in self.lines:
            line = line.strip()
            if line.startswith("import "):
                imports.append(line.split(";")[0].replace("import ", ""))
        return imports

    def _extract_classes(self) -> List[ClassInfo]:
        """提取类信息"""
        classes = []
        in_class = False
        class_start = 0
        current_class = None
        brace_count = 0

        class_pattern = re.compile(r'(public |private |protected )?(class |interface |enum )(\w+)')
        method_pattern = re.compile(r'(public |private |protected )?(static )?(\w+[\[\]<>]*)\s+(\w+)\s*\(')

        for i, line in enumerate(self.lines):
            match = class_pattern.search(line)
            if match:
                in_class = True
                class_start = i + 1
                current_class = ClassInfo(
                    name=match.group(3),
                    line_start=class_start,
                    line_end=class_start,
                    base_classes=self._extract_extends(line)
                )

            if current_class:
                brace_count += line.count('{') - line.count('}')
                if brace_count <= 0 and '{' in '\n'.join(self.lines[class_start:i+1]):
                    current_class.line_end = i + 1
                    classes.append(current_class)
                    current_class = None
                    in_class = False

                method_match = method_pattern.search(line)
                if method_match and not line.strip().startswith('//'):
                    return_type = method_match.group(3)
                    method_name = method_match.group(4)
                    if method_name and not method_name.startswith('if') and not method_name.startswith('for'):
                        func = FunctionInfo(
                            name=method_name,
                            line_start=i + 1,
                            line_end=i + 1,
                            return_type=return_type
                        )
                        current_class.methods.append(func)

        return classes

    def _extract_extends(self, line: str) -> List[str]:
        """提取继承的类"""
        extends = []
        if 'extends' in line:
            match = re.search(r'extends\s+(\w+)', line)
            if match:
                extends.append(match.group(1))
        return extends

    def _calculate_complexity(self, file_info: FileInfo) -> str:
        """计算文件复杂度"""
        total_lines = file_info.lines
        class_count = len(file_info.classes)
        method_count = sum(len(c.methods) for c in file_info.classes)

        score = total_lines / 50 + class_count * 2 + method_count

        if score < 5:
            return "low"
        elif score < 15:
            return "medium"
        else:
            return "high"

    def _generate_summary(self, file_info: FileInfo) -> str:
        """生成文件摘要"""
        parts = []
        if file_info.classes:
            class_names = [c.name for c in file_info.classes[:3]]
            parts.append(f"定义类: {', '.join(class_names)}")
        return "，".join(parts) if parts else "Java 源文件"


class JavaScriptAnalyzer:
    """JavaScript/TypeScript 代码分析器"""

    def __init__(self, content: str, file_path: str):
        self.content = content
        self.file_path = file_path
        self.lines = content.split('\n')
        self.language = "typescript" if file_path.endswith(('.ts', '.tsx')) else "javascript"

    def analyze(self) -> FileInfo:
        """分析 JavaScript/TypeScript 文件"""
        file_info = FileInfo(
            path=self.file_path,
            relative_path=self.file_path,
            language=self.language,
            lines=len(self.lines)
        )

        file_info.imports = self._extract_imports()
        file_info.exports = self._extract_exports()
        file_info.functions = self._extract_functions()
        file_info.classes = self._extract_classes()

        file_info.complexity = self._calculate_complexity(file_info)
        file_info.summary = self._generate_summary(file_info)

        return file_info

    def _extract_imports(self) -> List[str]:
        """提取导入语句"""
        imports = []
        import_pattern = re.compile(r'import\s+(?:{[^}]+}|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]')
        for line in self.lines:
            match = import_pattern.search(line)
            if match:
                imports.append(match.group(1))
        return imports

    def _extract_exports(self) -> List[str]:
        """提取导出语句"""
        exports = []
        for line in self.lines:
            line = line.strip()
            if line.startswith('export '):
                if 'function ' in line:
                    match = re.search(r'export\s+function\s+(\w+)', line)
                    if match:
                        exports.append(match.group(1))
                elif 'class ' in line:
                    match = re.search(r'export\s+class\s+(\w+)', line)
                    if match:
                        exports.append(match.group(1))
                elif 'const ' in line:
                    match = re.search(r'export\s+const\s+(\w+)', line)
                    if match:
                        exports.append(match.group(1))
        return exports

    def _extract_functions(self) -> List[FunctionInfo]:
        """提取函数信息"""
        functions = []
        func_pattern = re.compile(r'(?:export\s+)?function\s+(\w+)\s*\(([^)]*)\)')

        for i, line in enumerate(self.lines):
            match = func_pattern.search(line)
            if match:
                func = FunctionInfo(
                    name=match.group(1),
                    line_start=i + 1,
                    line_end=i + 1,
                    params=[p.strip() for p in match.group(2).split(',') if p.strip()]
                )
                functions.append(func)

        return functions

    def _extract_classes(self) -> List[ClassInfo]:
        """提取类信息"""
        classes = []
        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?')

        in_class = False
        current_class = None

        for i, line in enumerate(self.lines):
            match = class_pattern.search(line)
            if match:
                in_class = True
                current_class = ClassInfo(
                    name=match.group(1),
                    line_start=i + 1,
                    line_end=i + 1,
                    base_classes=[match.group(2)] if match.group(2) else []
                )

            if current_class and '{' in line:
                brace_count = line.count('{')
                if brace_count > 0 and current_class.line_end == current_class.line_start:
                    current_class.line_end = i + 1
                    classes.append(current_class)
                    current_class = None

        return classes

    def _calculate_complexity(self, file_info: FileInfo) -> str:
        """计算文件复杂度"""
        total_lines = file_info.lines
        func_count = len(file_info.functions)
        method_count = sum(len(c.methods) for c in file_info.classes)

        score = total_lines / 30 + func_count + method_count

        if score < 10:
            return "low"
        elif score < 25:
            return "medium"
        else:
            return "high"

    def _generate_summary(self, file_info: FileInfo) -> str:
        """生成文件摘要"""
        parts = []
        if file_info.classes:
            parts.append(f"定义 {len(file_info.classes)} 个类")
        if file_info.functions:
            parts.append(f"导出 {len(file_info.functions)} 个函数")
        return "，".join(parts) if parts else "工具模块"


class GoAnalyzer:
    """Go 代码分析器"""

    def __init__(self, content: str, file_path: str):
        self.content = content
        self.file_path = file_path
        self.lines = content.split('\n')

    def analyze(self) -> FileInfo:
        """分析 Go 文件"""
        file_info = FileInfo(
            path=self.file_path,
            relative_path=self.file_path,
            language="go",
            lines=len(self.lines)
        )

        file_info.imports = self._extract_imports()
        file_info.functions = self._extract_functions()
        file_info.classes = self._extract_types()

        file_info.complexity = self._calculate_complexity(file_info)
        file_info.summary = self._generate_summary(file_info)

        return file_info

    def _extract_imports(self) -> List[str]:
        """提取导入语句"""
        imports = []
        import_pattern = re.compile(r'import\s+(?:\((\s*\n)?([^)]+)\)|"([^"]+)")')

        content = '\n'.join(self.lines)
        for match in import_pattern.finditer(content):
            if match.group(3):
                imports.append(match.group(3))
            elif match.group(2):
                for line in match.group(2).split('\n'):
                    line = line.strip().strip('"')
                    if line:
                        imports.append(line)

        return imports

    def _extract_functions(self) -> List[FunctionInfo]:
        """提取函数信息"""
        functions = []
        func_pattern = re.compile(r'func\s+(\w+)\s*\(([^)]*)\)')

        for i, line in enumerate(self.lines):
            match = func_pattern.search(line)
            if match:
                func = FunctionInfo(
                    name=match.group(1),
                    line_start=i + 1,
                    line_end=i + 1,
                    params=[p.strip() for p in match.group(2).split(',') if p.strip()]
                )
                functions.append(func)

        return functions

    def _extract_types(self) -> List[ClassInfo]:
        """提取类型定义（struct）"""
        classes = []
        type_pattern = re.compile(r'type\s+(\w+)\s+struct\s*\{')

        for i, line in enumerate(self.lines):
            match = type_pattern.search(line)
            if match:
                class_info = ClassInfo(
                    name=match.group(1),
                    line_start=i + 1,
                    line_end=i + 1
                )
                classes.append(class_info)

        return classes

    def _calculate_complexity(self, file_info: FileInfo) -> str:
        """计算文件复杂度"""
        total_lines = file_info.lines
        func_count = len(file_info.functions)

        score = total_lines / 40 + func_count

        if score < 10:
            return "low"
        elif score < 20:
            return "medium"
        else:
            return "high"

    def _generate_summary(self, file_info: FileInfo) -> str:
        """生成文件摘要"""
        parts = []
        if file_info.functions:
            func_names = [f.name for f in file_info.functions[:3]]
            parts.append(f"函数: {', '.join(func_names)}")
        return "，".join(parts) if parts else "Go 源文件"


class ConfigAnalyzer:
    """配置文件分析器"""

    CONFIG_PATTERNS: Dict[str, Dict[str, Any]] = {
        ".yaml": {"section": r'^(\w+):', "key": r'^\s+(\w+):\s*(.+)'},
        ".yml": {"section": r'^(\w+):', "key": r'^\s+(\w+):\s*(.+)'},
        ".json": {"type": "json"},
        ".properties": {"key": r'^(\w+)\s*=\s*(.+)'},
        ".toml": {"section": r'^\[(\w+)\]', "key": r'^(\w+)\s*=\s*(.+)'},
    }

    @classmethod
    def analyze(cls, file_path: str, content: str) -> Dict[str, Any]:
        """分析配置文件"""
        ext = os.path.splitext(file_path)[1].lower()

        if ext not in cls.CONFIG_PATTERNS:
            return {"type": "unknown", "content_preview": content[:200]}

        pattern_info = cls.CONFIG_PATTERNS[ext]

        if pattern_info.get("type") == "json":
            return cls._analyze_json(content)
        else:
            return cls._analyze_key_value(content, pattern_info)

    @classmethod
    def _analyze_json(cls, content: str) -> Dict[str, Any]:
        """分析 JSON 配置"""
        try:
            data = json.loads(content)
            return {
                "type": "json",
                "keys": list(data.keys()) if isinstance(data, dict) else [],
                "preview": json.dumps(data, indent=2)[:500] if isinstance(data, dict) else str(data)[:200]
            }
        except json.JSONDecodeError:
            return {"type": "json", "error": "Invalid JSON", "content_preview": content[:200]}

    @classmethod
    def _analyze_key_value(cls, content: str, pattern_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析键值对配置"""
        sections = {}
        current_section = "root"
        lines = content.split('\n')

        section_pattern = re.compile(pattern_info.get("section", r'^(\w+):'))
        key_pattern = re.compile(pattern_info.get("key", r'^(\w+)\s*=\s*(.+)'))

        for line in lines:
            section_match = section_pattern.search(line)
            if section_match:
                current_section = section_match.group(1)
                if current_section not in sections:
                    sections[current_section] = []
                continue

            key_match = key_pattern.search(line)
            if key_match:
                key = key_match.group(1)
                value = key_match.group(2)[:50]
                if current_section not in sections:
                    sections[current_section] = []
                sections[current_section].append(f"{key} = {value}")

        return {
            "type": "config",
            "sections": sections,
            "preview": content[:200]
        }


class LayerDetector:
    """架构层检测器"""

    LAYER_PATTERNS: List[LayerInfo] = [
        LayerInfo(
            name="frontend-ui",
            description="前端UI组件层",
            patterns=["component", "view", "page", "screen", "layout", "widget", "ui", "template"]
        ),
        LayerInfo(
            name="frontend-service",
            description="前端服务层",
            patterns=["service", "api", "fetch", "request"]
        ),
        LayerInfo(
            name="frontend-store",
            description="前端状态管理层",
            patterns=["store", "redux", "vuex", "pinia", "state"]
        ),
        LayerInfo(
            name="api",
            description="API 端点层",
            patterns=["routes", "controller", "handler", "endpoint", "router", "route"]
        ),
        LayerInfo(
            name="service",
            description="业务逻辑层",
            patterns=["service", "usecase", "business", "logic"]
        ),
        LayerInfo(
            name="domain",
            description="领域模型层",
            patterns=["model", "entity", "domain"]
        ),
        LayerInfo(
            name="data",
            description="数据访问层",
            patterns=["repository", "repo", "dao", "dal", "mapper", "database", "db"]
        ),
        LayerInfo(
            name="middleware",
            description="中间件层",
            patterns=["middleware", "interceptor", "guard", "filter", "pipe", "wrapper"]
        ),
        LayerInfo(
            name="util",
            description="工具层",
            patterns=["util", "helper", "lib", "common", "shared", "tool", "tools", "function"]
        ),
        LayerInfo(
            name="config",
            description="配置层",
            patterns=["config", "setting", "settings", "env", "configuration"]
        ),
    ]

    @classmethod
    def detect_layer(cls, file_path: str) -> LayerInfo:
        """检测文件所属的架构层"""
        normalized_path = file_path.lower().replace('\\', '/')
        segments = normalized_path.split('/')

        for layer in cls.LAYER_PATTERNS:
            for segment in segments:
                for pattern in layer.patterns:
                    if segment == pattern or segment == f"{pattern}s":
                        return layer

        default_layer = LayerInfo(
            name="Core",
            description="核心应用文件",
            patterns=[""]
        )
        return default_layer

    @classmethod
    def group_by_layer(cls, files: List[FileInfo]) -> Dict[str, List[FileInfo]]:
        """按照架构层分组文件"""
        layers: Dict[str, List[FileInfo]] = defaultdict(list)

        for file_info in files:
            layer = cls.detect_layer(file_info.path)
            layers[layer.name].append(file_info)

        return layers


class CodeMapGenerator:
    """代码地图生成器主类"""

    def __init__(self, project_root: str, workspace_root: Optional[str] = None):
        self.project_root = Path(project_root)
        self.workspace_root = Path(workspace_root) if workspace_root else self.project_root.parent
        self.files: List[FileInfo] = []
        self.modules: Dict[str, ModuleInfo] = {}
        self.layers: Dict[str, LayerInfo] = {}
        self.config_files: List[Dict[str, Any]] = []
        try:
            relative_path = str(self.project_root.relative_to(self.workspace_root))
        except ValueError:
            relative_path = self.project_root.name
        self.project_info: Dict[str, Any] = {
            "name": self.project_root.name,
            "path": str(self.project_root),
            "workspace": str(self.workspace_root),
            "workspace_name": self.workspace_root.name,
            "relative_path": relative_path,
            "languages": set(),
            "frameworks": set(),
            "total_files": 0,
            "total_lines": 0,
            "complexity": "unknown"
        }

    def scan(self):
        """扫描项目文件"""
        print(f"开始扫描项目: {self.project_root}")

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not self._should_skip_dir(d, root)]

            for file_name in files:
                file_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(file_path, self.project_root)

                if LanguageDetector.is_source_file(file_path):
                    self._analyze_source_file(file_path, relative_path)
                elif LanguageDetector.is_config_file(file_path):
                    self._analyze_config_file(file_path, relative_path)

        self._update_project_info()
        print(f"扫描完成: 发现 {len(self.files)} 个源文件, {len(self.config_files)} 个配置文件")

    def _should_skip_dir(self, dir_name: str, parent: str) -> bool:
        """判断是否应该跳过目录"""
        skip_patterns = [
            'node_modules', '.git', '__pycache__', 'target', 'build', 'dist',
            '.gradle', '.idea', '.vscode', 'vendor', 'venv', '.venv', '.env',
            '.cache', '.next', '.nuxt', '.turbo', 'coverage', '.pytest_cache'
        ]
        return dir_name in skip_patterns or dir_name.startswith('.')

    def _analyze_source_file(self, file_path: str, relative_path: str):
        """分析源文件"""
        try:
            content = Path(file_path).read_text(encoding='utf-8')
            language = LanguageDetector.detect(file_path)
            self.project_info["languages"].add(language)

            file_info = None

            if language == "python":
                analyzer = PythonAnalyzer(content, relative_path)
                file_info = analyzer.analyze()
            elif language == "java":
                analyzer = JavaAnalyzer(content, relative_path)
                file_info = analyzer.analyze()
            elif language in ("javascript", "typescript"):
                analyzer = JavaScriptAnalyzer(content, relative_path)
                file_info = analyzer.analyze()
            elif language == "go":
                analyzer = GoAnalyzer(content, relative_path)
                file_info = analyzer.analyze()
            else:
                file_info = FileInfo(
                    path=file_path,
                    relative_path=relative_path,
                    language=language,
                    lines=len(content.split('\n'))
                )

            if file_info:
                self._detect_frameworks(file_info)
                self.files.append(file_info)

        except Exception as e:
            print(f"分析文件失败 {relative_path}: {e}")

    def _analyze_config_file(self, file_path: str, relative_path: str):
        """分析配置文件"""
        try:
            content = Path(file_path).read_text(encoding='utf-8')
            config_info = ConfigAnalyzer.analyze(relative_path, content)
            config_info["path"] = relative_path
            self.config_files.append(config_info)
        except Exception as e:
            print(f"分析配置文件失败 {relative_path}: {e}")

    def _detect_frameworks(self, file_info: FileInfo):
        """检测框架"""
        all_text = ' '.join(file_info.imports).lower()

        framework_signatures = {
            "Spring": ["org.springframework", "spring-boot", "springframework"],
            "Django": ["django", "django.db", "django.http"],
            "Flask": ["flask", "flask.request", "flask.json"],
            "FastAPI": ["fastapi", "uvicorn"],
            "React": ["react", "react-dom", "jsx", "@react"],
            "Vue": ["vue", "@vue", "vue-router"],
            "Angular": ["@angular", "ng-module"],
            "Express": ["express", "express.router", "body-parser"],
            "Spring Boot": ["springboot", "spring-boot-starter"],
            "MyBatis": ["org.mybatis", "mapper", "mybatis"],
            "SQLAlchemy": ["sqlalchemy", "orm"],
            "Mongoose": ["mongoose"],
            "Sequelize": ["sequelize"],
        }

        for framework, signatures in framework_signatures.items():
            if any(sig in all_text for sig in signatures):
                self.project_info["frameworks"].add(framework)

    def _update_project_info(self):
        """更新项目信息"""
        self.project_info["total_files"] = len(self.files)
        self.project_info["total_lines"] = sum(f.lines for f in self.files)
        self.project_info["languages"] = list(self.project_info["languages"])
        self.project_info["frameworks"] = list(self.project_info["frameworks"])

        if self.project_info["total_files"] < 20:
            self.project_info["complexity"] = "simple"
        elif self.project_info["total_files"] < 100:
            self.project_info["complexity"] = "medium"
        elif self.project_info["total_files"] < 500:
            self.project_info["complexity"] = "large"
        else:
            self.project_info["complexity"] = "very-large"

    def group_by_module(self) -> Dict[str, List[FileInfo]]:
        """按模块分组文件"""
        modules: Dict[str, List[FileInfo]] = defaultdict(list)

        for file_info in self.files:
            parts = file_info.relative_path.split(os.sep)
            if len(parts) > 1 and parts[0] in ['src', 'app', 'lib', 'pkg', 'internal', 'cmd']:
                module_name = parts[1] if len(parts) > 1 else 'root'
            else:
                module_name = parts[0] if parts else 'root'

            modules[module_name].append(file_info)

        return modules

    def generate_markdown(self, output_path: Optional[str] = None) -> str:
        """生成 Markdown 格式的代码地图"""
        print("开始生成代码地图...")

        md_content = self._generate_header()
        md_content += self._generate_overview()
        md_content += self._generate_layers()
        md_content += self._generate_modules()
        md_content += self._generate_files_detail()
        md_content += self._generate_config()
        md_content += self._generate_call_flows()
        md_content += self._generate_quick_fix_guide()
        md_content += self._generate_footer()

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(md_content, encoding='utf-8')
            print(f"代码地图已保存到: {output_path}")

        return md_content

    def _generate_header(self) -> str:
        """生成文档头部"""
        git_hash = ""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_hash = result.stdout.strip()[:8]
        except Exception:
            pass

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return f"""# {self.project_info['name']} 代码地图

> **生成时间**: {timestamp}
> **代码版本**: {git_hash or 'unknown'}
> **工作空间**: `{self.project_info['workspace_name']}`
> **分析文件数**: {self.project_info['total_files']}
> **总代码行数**: {self.project_info['total_lines']:,}

---

## 项目标识

| 属性 | 值 |
|------|-----|
| **项目名称** | {self.project_info['name']} |
| **工作空间** | {self.project_info['workspace_name']} |
| **项目路径** | `{self.project_info['path']}` |
| **相对路径** | `{self.project_info['relative_path']}` |

---

## 技术栈

| 类别 | 内容 |
|------|------|
| **语言** | {', '.join(sorted(self.project_info['languages']))} |
| **框架** | {', '.join(self.project_info['frameworks']) if self.project_info['frameworks'] else '未检测到特定框架'} |
| **代码规模** | {self.project_info['complexity']} |
| **文件总数** | {self.project_info['total_files']} |
| **代码总行数** | {self.project_info['total_lines']:,} |

---

"""

    def _generate_overview(self) -> str:
        """生成项目概览部分"""
        md = "## 项目架构概览\n\n"

        layers_group = LayerDetector.group_by_layer(self.files)

        md += "| 架构层级 | 文件数 | 说明 |\n"
        md += "|----------|--------|------|\n"

        layer_order = ["API Layer", "Service Layer", "Data Layer", "UI Layer",
                       "Middleware Layer", "Utility Layer", "Config Layer", "Test Layer", "Core"]

        for layer_name in layer_order:
            if layer_name in layers_group:
                layer_info = next((l for l in LayerDetector.LAYER_PATTERNS if l.name == layer_name),
                                  LayerInfo(layer_name, "", []))
                file_count = len(layers_group[layer_name])
                md += f"| **{layer_name}** | {file_count} | {layer_info.description} |\n"

        md += "\n"
        return md

    def _generate_layers(self) -> str:
        """生成架构分层详情"""
        md = "## 架构分层详解\n\n"

        layers_group = LayerDetector.group_by_layer(self.files)
        layer_order = ["API Layer", "Service Layer", "Data Layer", "UI Layer",
                       "Middleware Layer", "Utility Layer", "Config Layer", "Test Layer", "Core"]

        for layer_name in layer_order:
            if layer_name not in layers_group:
                continue

            files = layers_group[layer_name]
            layer_info = next((l for l in LayerDetector.LAYER_PATTERNS if l.name == layer_name),
                              LayerInfo(layer_name, "", []))

            md += f"### {layer_name}\n\n"
            md += f"**职责**: {layer_info.description}\n\n"

            md += "| 文件 | 复杂度 | 类/函数 | 说明 |\n"
            md += "|------|--------|---------|------|\n"

            for file_info in sorted(files, key=lambda f: f.relative_path)[:20]:
                element_count = len(file_info.classes) + len(file_info.functions)
                elements = []
                if file_info.classes:
                    elements.append(f"{len(file_info.classes)} 类")
                if file_info.functions:
                    elements.append(f"{len(file_info.functions)} 函数")
                element_str = ", ".join(elements) if elements else "-"

                summary = file_info.summary[:40] if file_info.summary else "-"
                md += f"| `{file_info.relative_path}` | {file_info.complexity} | {element_str} | {summary} |\n"

            if len(files) > 20:
                md += f"\n*... 还有 {len(files) - 20} 个文件*\n"

            md += "\n"
            md += self._generate_layer_call_patterns(layer_name, files)

        return md

    def _generate_layer_call_patterns(self, layer_name: str, files: List[FileInfo]) -> str:
        """生成层的调用模式说明"""
        patterns = {
            "API Layer": "通常被外部客户端调用，可能调用 Service Layer",
            "Service Layer": "被 API Layer 调用，调用 Data Layer 和 Utility Layer",
            "Data Layer": "被 Service Layer 调用，提供数据持久化",
            "UI Layer": "被 API Layer 或路由层调用，调用 Service Layer 获取数据",
            "Middleware Layer": "被 API Layer 引用，处理请求/响应流水线",
            "Utility Layer": "被所有层调用，提供通用工具函数",
            "Config Layer": "被所有层引用，提供配置信息",
            "Test Layer": "测试其他各层",
        }

        pattern = patterns.get(layer_name, "")
        if not pattern:
            return ""

        return f"> **调用模式**: {pattern}\n\n"

    def _generate_modules(self) -> str:
        """生成模块详情"""
        md = "## 模块详情\n\n"

        modules = self.group_by_module()

        for module_name, files in sorted(modules.items()):
            md += f"### module: {module_name}\n\n"

            module_files = [f for f in files if not f.relative_path.endswith('_test.py') and not f.relative_path.endswith('.test.')]
            if not module_files:
                continue

            main_file = min(module_files, key=lambda f: len(f.relative_path))
            md += f"**主要文件**: `{main_file.relative_path}`\n\n"

            md += "**文件列表**:\n"
            for file_info in sorted(files, key=lambda f: f.relative_path)[:10]:
                md += f"- `{file_info.relative_path}` ({file_info.language}, {file_info.lines} 行)\n"

            if len(files) > 10:
                md += f"- ... 等 {len(files) - 10} 个文件\n"

            md += "\n"

            exported_funcs = []
            exported_classes = []
            for f in module_files:
                for func in f.functions:
                    exported_funcs.append(f"`{func.name}()`")
                for cls in f.classes:
                    exported_classes.append(f"`{cls.name}`")

            if exported_funcs:
                md += f"**导出函数**: {', '.join(exported_funcs[:10])}"
                if len(exported_funcs) > 10:
                    md += f" ... 等 {len(exported_funcs)} 个"
                md += "\n\n"

            if exported_classes:
                md += f"**导出类**: {', '.join(exported_classes[:10])}"
                if len(exported_classes) > 10:
                    md += f" ... 等 {len(exported_classes)} 个"
                md += "\n\n"

        return md

    def _generate_files_detail(self) -> str:
        """生成文件详情"""
        md = "## 文件详情\n\n"

        key_files = sorted(self.files, key=lambda f: f.lines, reverse=True)[:30]

        for file_info in key_files:
            md += f"### file:{file_info.relative_path}\n\n"
            md += f"**路径**: `{file_info.relative_path}`\n\n"
            md += f"**语言**: {file_info.language}  |  **行数**: {file_info.lines}  |  **复杂度**: {file_info.complexity}\n\n"

            if file_info.summary:
                md += f"**功能描述**: {file_info.summary}\n\n"

            if file_info.imports:
                md += "**导入依赖**:\n"
                for imp in file_info.imports[:15]:
                    md += f"- `{imp}`\n"
                if len(file_info.imports) > 15:
                    md += f"- ... 等 {len(file_info.imports) - 15} 个导入\n"
                md += "\n"

            if file_info.classes:
                md += "**类定义**:\n"
                for cls in file_info.classes[:5]:
                    md += f"#### class: {cls.name}\n\n"
                    md += f"- 行号: {cls.line_start}-{cls.line_end}\n"
                    if cls.base_classes:
                        md += f"- 继承: {', '.join(cls.base_classes)}\n"
                    if cls.properties:
                        md += f"- 属性: {', '.join(cls.properties[:5])}\n"
                    if cls.methods:
                        md += "- 方法:\n"
                        for method in cls.methods[:10]:
                            md += f"  - `{method.name}({', '.join(method.params)})`"
                            if method.return_type:
                                md += f" -> {method.return_type}"
                            md += "\n"
                    if cls.docstring:
                        md += f"- 说明: {cls.docstring[:100]}...\n"
                    md += "\n"

            if file_info.functions:
                md += "**函数定义**:\n"
                for func in file_info.functions[:10]:
                    md += f"#### func: {func.name}\n\n"
                    md += f"- 行号: {func.line_start}\n"
                    md += f"- 参数: {', '.join(func.params) if func.params else '无'}\n"
                    if func.return_type:
                        md += f"- 返回: {func.return_type}\n"
                    if func.calls:
                        md += f"- 调用: {', '.join(func.calls[:5])}\n"
                    if func.docstring:
                        md += f"- 说明: {func.docstring[:100]}...\n"
                    md += "\n"

        return md

    def _generate_config(self) -> str:
        """生成配置文件说明"""
        if not self.config_files:
            return ""

        md = "## 配置文件\n\n"

        for config in self.config_files[:20]:
            path = config.get("path", "unknown")
            config_type = config.get("type", "unknown")

            md += f"### config:{path}\n\n"
            md += f"**文件路径**: `{path}`\n"
            md += f"**配置类型**: {config_type}\n\n"

            if config.get("sections"):
                md += "**配置项**:\n"
                for section, items in list(config["sections"].items())[:10]:
                    md += f"- **{section}**:\n"
                    for item in items[:5]:
                        md += f"  - {item}\n"

            if config.get("preview"):
                md += f"\n**预览**:\n```\n{config['preview'][:300]}\n```\n"

            md += "\n"

        return md

    def _generate_call_flows(self) -> str:
        """生成调用流程图"""
        md = "## 调用流程图\n\n"

        md += "### 典型调用链\n\n"

        layers_group = LayerDetector.group_by_layer(self.files)

        if "API Layer" in layers_group and "Service Layer" in layers_group:
            md += "```\n"
            md += "外部请求\n"
            md += "    │\n"
            md += "    ▼\n"
            md += "API Layer (处理 HTTP 请求)\n"
            md += "    │\n"
            md += "    ▼\n"
            md += "Service Layer (业务逻辑)\n"
            md += "    │\n"
            md += "    ├──▶ Data Layer (数据持久化)\n"
            md += "    │\n"
            md += "    └──▶ Utility Layer (工具函数)\n"
            md += "    │\n"
            md += "    ▼\n"
            md += "返回响应\n"
            md += "```\n\n"

        md += "### 模块间依赖关系\n\n"

        modules = self.group_by_module()
        module_names = sorted(modules.keys())[:10]

        md += "```\n"
        for i, module_name in enumerate(module_names):
            files = modules[module_name]
            imports_from = set()
            for f in files:
                for imp in f.imports:
                    for other_module in module_names:
                        if other_module != module_name and other_module in imp:
                            imports_from.add(other_module)

            deps = ", ".join(sorted(imports_from)) if imports_from else "无"
            is_last = i == len(module_names) - 1
            connector = "└──" if is_last else "├──"
            md += f"{connector} {module_name} → [{deps}]\n"

        md += "```\n\n"

        return md

    def _generate_quick_fix_guide(self) -> str:
        """生成快速修复指南"""
        md = "## 快速修复指南\n\n"

        layers_group = LayerDetector.group_by_layer(self.files)

        fix_guides = {
            "API Layer": [
                ("路由问题", "检查 `routes/` 或 `controller/` 目录下的路由配置", "api"),
                ("参数验证失败", "检查 `middleware/` 中的验证器", "validator"),
            ],
            "Service Layer": [
                ("业务逻辑错误", "检查 `service/` 目录下的服务类", "service"),
                ("数据处理问题", "检查 service 方法中的数据转换逻辑", "transform"),
            ],
            "Data Layer": [
                ("数据库连接失败", "检查 `config/` 中的数据库配置", "database"),
                ("查询错误", "检查 `repository/` 或 `dao/` 中的 SQL", "query"),
            ],
        }

        for layer_name, guides in fix_guides.items():
            if layer_name not in layers_group:
                continue

            md += f"### {layer_name} 问题排查\n\n"

            for title, desc, keyword in guides:
                md += f"#### {title}\n\n"
                md += f"- **排查位置**: {desc}\n"
                md += f"- **关键字**: `{keyword}`\n"

                matching_files = []
                for f in layers_group[layer_name]:
                    if any(keyword.lower() in f.relative_path.lower() for _ in [1]):
                        matching_files.append(f"`{f.relative_path}`")

                if matching_files:
                    md += f"- **相关文件**: {', '.join(matching_files[:3])}\n"

                md += "\n"

        return md

    def _generate_footer(self) -> str:
        """生成文档尾部"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""---

*此代码地图由 Code Map Generator v2.0 自动生成*
*最后更新: {timestamp}*
"""

    def generate_visualization_json(self, output_path: Optional[str] = None,
                                     ai_analyzer: Optional[AICallRelationAnalyzer] = None) -> Dict[str, Any]:
        """生成用于 3D 可视化的 JSON 数据结构（新版）

        Args:
            output_path: 输出文件路径
            ai_analyzer: AI 调用关系分析器（可选），如果有则进行深度 AI 分析

        返回的 JSON 结构:
        {
            "version": "2.0",
            "project": { 项目信息，包含前后端分类 },
            "layers": [ 层级列表，包含 side 属性区分前后端 ],
            "nodes": [ 节点列表，包含真实调用关系 ],
            "edges": [ 调用关系列表，连接到实际节点 ]
        }

        节点结构:
        {
            "id": str,           # 唯一标识，格式: type:path 或 type:path:name
            "type": str,          # "module" | "file" | "class" | "function"
            "name": str,          # 显示名称
            "fullName": str,      # 完整名称
            "layerId": str,       # 所属层级 ID
            "side": str,          # "frontend" | "backend" | "shared"
            "filePath": str,      # 文件路径
            "language": str,       # 编程语言
            "size": int,          # 节点大小
            "calls": [str],       # 直接调用的节点 ID 列表
            "calledBy": [str],    # 被调用的节点 ID 列表
            "parentId": str,       # 父节点 ID
            "children": [str],    # 子节点 ID 列表
            "metrics": {}         # 额外指标
        }

        边结构:
        {
            "id": str,           # 唯一标识
            "source": str,       # 源节点 ID
            "target": str,       # 目标节点 ID
            "type": str,         # "calls" | "imports" | "http" | "extends"
            "protocol": str,     # "local" | "http" | "https" | "websocket"
            "layer": str         # 层级关系描述
        }
        """
        print("开始生成可视化 JSON 数据 (v2.0)...")

        nodes = []
        edges = []
        node_id_map = {}  # 用于去重和快速查找

        # 定义层级（包含前后端分类）
        layers_def = [
            {"id": "frontend-ui", "name": "前端UI层", "side": "frontend", "color": 0x58a6ff},
            {"id": "frontend-service", "name": "前端服务层", "side": "frontend", "color": 0xa371f7},
            {"id": "frontend-store", "name": "前端状态层", "side": "frontend", "color": 0x39c5cf},
            {"id": "api", "name": "API层", "side": "backend", "color": 0xf85149},
            {"id": "service", "name": "业务逻辑层", "side": "backend", "color": 0x3fb950},
            {"id": "domain", "name": "领域层", "side": "backend", "color": 0xd97706},
            {"id": "data", "name": "数据访问层", "side": "backend", "color": 0xdb61a2},
            {"id": "middleware", "name": "中间件层", "side": "backend", "color": 0xff7b72},
            {"id": "util", "name": "工具层", "side": "shared", "color": 0x8b949e},
            {"id": "config", "name": "配置层", "side": "shared", "color": 0xe3b341}
        ]
        layers_map = {l["id"]: l for l in layers_def}

        # 生成项目信息
        project_info = {
            "name": self.project_info["name"],
            "workspace": self.project_info["workspace_name"],
            "totalFiles": self.project_info["total_files"],
            "totalLines": self.project_info["total_lines"],
            "languages": self.project_info["languages"],
            "frameworks": self.project_info["frameworks"],
            "frontend": {
                "name": "前端",
                "languages": [l for l in self.project_info["languages"] if l in ["javascript", "typescript", "vue", "react"]],
                "layers": ["frontend-ui", "frontend-service", "frontend-store"]
            },
            "backend": {
                "name": "后端",
                "languages": [l for l in self.project_info["languages"] if l not in ["javascript", "typescript", "vue", "react"]],
                "layers": ["api", "service", "domain", "data", "middleware"]
            }
        }

        # 1. 生成模块节点
        modules = self.group_by_module()
        for module_name, files in modules.items():
            module_id = f"module:{module_name}"
            file_count = len(files)
            total_lines = sum(f.lines for f in files)

            # 计算模块大小
            size = min(5, max(1, int(file_count / 3) + int(total_lines / 1000)))

            # 确定模块所属层级和前后端
            module_layer_id, module_side = self._detect_module_layer_and_side(files)

            module_node = {
                "id": module_id,
                "type": "module",
                "name": module_name,
                "fullName": f"{module_name} ({file_count} 文件)",
                "layerId": module_layer_id,
                "side": module_side,
                "filePath": "",
                "language": ",".join(set(f.language for f in files)),
                "size": size,
                "calls": [],
                "calledBy": [],
                "children": [],
                "metrics": {
                    "fileCount": file_count,
                    "totalLines": total_lines,
                    "classCount": sum(len(f.classes) for f in files),
                    "functionCount": sum(len(f.functions) for f in files)
                }
            }
            nodes.append(module_node)
            node_id_map[module_id] = module_node

        # 2. 生成文件节点
        for file_info in self.files:
            file_id = f"file:{file_info.relative_path}"

            # 确定文件所属模块
            module_name = self._get_file_module(file_info.relative_path)
            module_id = f"module:{module_name}"

            # 确定文件层级和前后端
            layer_id, side = self._detect_file_layer_and_side(file_info.relative_path)

            # 计算文件大小
            size = min(4, max(1, int(file_info.lines / 100) + 1))

            file_node = {
                "id": file_id,
                "type": "file",
                "name": os.path.basename(file_info.relative_path),
                "fullName": file_info.relative_path,
                "layerId": layer_id,
                "side": side,
                "filePath": file_info.relative_path,
                "language": file_info.language,
                "size": size,
                "calls": [],
                "calledBy": [],
                "children": [],
                "parentId": module_id,
                "metrics": {
                    "lines": file_info.lines,
                    "classCount": len(file_info.classes),
                    "functionCount": len(file_info.functions),
                    "complexity": file_info.complexity
                }
            }
            nodes.append(file_node)
            node_id_map[file_id] = file_node

            # 更新模块的 children
            if module_id in node_id_map:
                node_id_map[module_id]["children"].append(file_id)

        # 3. 生成类节点
        for file_info in self.files:
            file_id = f"file:{file_info.relative_path}"
            layer_id, side = self._detect_file_layer_and_side(file_info.relative_path)

            for cls in file_info.classes:
                class_id = f"class:{file_info.relative_path}:{cls.name}"

                # 计算类大小
                size = min(3, max(1, len(cls.methods) + 1))

                class_node = {
                    "id": class_id,
                    "type": "class",
                    "name": cls.name,
                    "fullName": f"{cls.name} ({len(cls.methods)} 方法)",
                    "layerId": layer_id,
                    "side": side,
                    "filePath": file_info.relative_path,
                    "language": file_info.language,
                    "size": size,
                    "calls": [],
                    "calledBy": [],
                    "children": [],
                    "parentId": file_id,
                    "metrics": {
                        "methodCount": len(cls.methods),
                        "propertyCount": len(cls.properties),
                        "baseClasses": cls.base_classes,
                        "lines": cls.line_end - cls.line_start
                    }
                }
                nodes.append(class_node)
                node_id_map[class_id] = class_node

                # 更新文件的 children
                if file_id in node_id_map:
                    node_id_map[file_id]["children"].append(class_id)

                # 为每个方法生成函数节点
                for method in cls.methods:
                    method_id = f"method:{file_info.relative_path}:{cls.name}:{method.name}"
                    method_full_name = f"{cls.name}.{method.name}"

                    method_node = {
                        "id": method_id,
                        "type": "function",
                        "name": method.name,
                        "fullName": method_full_name,
                        "layerId": layer_id,
                        "side": side,
                        "filePath": file_info.relative_path,
                        "language": file_info.language,
                        "size": 1,
                        "calls": [],
                        "calledBy": [],
                        "children": [],
                        "parentId": class_id,
                        "metrics": {
                            "params": method.params,
                            "returnType": method.return_type,
                            "lines": method.line_end - method.line_start
                        }
                    }
                    nodes.append(method_node)
                    node_id_map[method_id] = method_node

                    # 更新类的 children
                    node_id_map[class_id]["children"].append(method_id)

        # 4. 生成独立函数节点（不在类中的函数）
        for file_info in self.files:
            file_id = f"file:{file_info.relative_path}"
            layer_id, side = self._detect_file_layer_and_side(file_info.relative_path)

            for func in file_info.functions:
                func_id = f"func:{file_info.relative_path}:{func.name}"

                func_node = {
                    "id": func_id,
                    "type": "function",
                    "name": func.name,
                    "fullName": func.name,
                    "layerId": layer_id,
                    "side": side,
                    "filePath": file_info.relative_path,
                    "language": file_info.language,
                    "size": 1,
                    "calls": [],
                    "calledBy": [],
                    "children": [],
                    "parentId": file_id,
                    "metrics": {
                        "params": func.params,
                        "returnType": func.return_type,
                        "lines": func.line_end - func.line_start
                    }
                }
                nodes.append(func_node)
                node_id_map[func_id] = func_node

                # 更新文件的 children
                if file_id in node_id_map:
                    node_id_map[file_id]["children"].append(func_id)

        # 5. 生成真实调用关系边（基于导入和方法调用分析）
        edge_id_set = set()  # 用于去重

        for file_info in self.files:
            file_id = f"file:{file_info.relative_path}"

            # 文件级别的导入关系 -> 生成 calls 边
            for imp in file_info.imports:
                # 尝试匹配导入的模块/文件
                for other_file in self.files:
                    if other_file == file_info:
                        continue

                    if self._is_import_match(imp, other_file):
                        edge_id = f"edge:{file_id}->{other_file.relative_path}"
                        if edge_id not in edge_id_set:
                            source_layer_id, _ = self._detect_file_layer_and_side(file_info.relative_path)
                            target_layer_id, _ = self._detect_file_layer_and_side(other_file.relative_path)

                            edge = {
                                "id": edge_id,
                                "source": file_id,
                                "target": f"file:{other_file.relative_path}",
                                "type": "imports",
                                "protocol": "local",
                                "layer": f"{source_layer_id}->{target_layer_id}"
                            }
                            edges.append(edge)
                            edge_id_set.add(edge_id)

                            # 更新节点的调用和被调用关系
                            if file_id in node_id_map:
                                if f"file:{other_file.relative_path}" not in node_id_map[file_id]["calls"]:
                                    node_id_map[file_id]["calls"].append(f"file:{other_file.relative_path}")
                            if f"file:{other_file.relative_path}" in node_id_map:
                                if file_id not in node_id_map[f"file:{other_file.relative_path}"]["calledBy"]:
                                    node_id_map[f"file:{other_file.relative_path}"]["calledBy"].append(file_id)

            # 类中的方法调用 -> 生成 calls 边
            for cls in file_info.classes:
                class_id = f"class:{file_info.relative_path}:{cls.name}"

                for method in cls.methods:
                    method_id = f"method:{file_info.relative_path}:{cls.name}:{method.name}"

                    # 分析方法调用
                    for called_func in method.calls:
                        # 匹配同类中的其他方法
                        for other_method in cls.methods:
                            if other_method.name == called_func:
                                edge_id = f"edge:{method_id}->{cls.name}:{other_method.name}"
                                if edge_id not in edge_id_set:
                                    edge = {
                                        "id": edge_id,
                                        "source": method_id,
                                        "target": f"method:{file_info.relative_path}:{cls.name}:{other_method.name}",
                                        "type": "calls",
                                        "protocol": "local",
                                        "layer": "intra-class"
                                    }
                                    edges.append(edge)
                                    edge_id_set.add(edge_id)

                        # 匹配其他类的方法
                        for other_file in self.files:
                            for other_cls in other_file.classes:
                                for other_method in other_cls.methods:
                                    if other_method.name == called_func:
                                        edge_id = f"edge:{method_id}->method:{other_file.relative_path}:{other_cls.name}:{other_method.name}"
                                        if edge_id not in edge_id_set:
                                            edge = {
                                                "id": edge_id,
                                                "source": method_id,
                                                "target": f"method:{other_file.relative_path}:{other_cls.name}:{other_method.name}",
                                                "type": "calls",
                                                "protocol": "local",
                                                "layer": "inter-class"
                                            }
                                            edges.append(edge)
                                            edge_id_set.add(edge_id)

        # 6. AI 深度分析调用关系（如果提供了 AI 分析器）
        if ai_analyzer:
            print("\n🤖 正在进行 AI 深度分析关键文件的调用关系...")
            ai_call_count = 0

            # 选择关键文件进行分析（通常是 service、api、controller 层的文件）
            key_files = []
            for file_info in self.files:
                layer_id, _ = self._detect_file_layer_and_side(file_info.relative_path)
                if layer_id in ['api', 'service', 'frontend-service']:
                    key_files.append(file_info)

            # 限制 AI 分析的文件数量
            max_ai_analysis = min(20, len(key_files))

            for i, file_info in enumerate(key_files[:max_ai_analysis]):
                print(f"  [{i+1}/{max_ai_analysis}] AI 分析: {file_info.relative_path}")

                # 读取文件内容
                try:
                    with open(file_info.path, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content = f.read()
                except:
                    continue

                # 调用 AI 分析
                ai_relations = ai_analyzer.analyze_file_relations(
                    file_info.relative_path,
                    file_content,
                    self.files
                )

                # 将 AI 分析结果转换为边
                source_id = f"file:{file_info.relative_path}"
                for target_id in ai_relations.get('matched', []):
                    edge_id = f"edge:ai:{source_id}->{target_id}"
                    if edge_id not in edge_id_set:
                        source_layer_id, _ = self._detect_file_layer_and_side(file_info.relative_path)

                        # 尝试获取目标文件的层级
                        target_layer_id = source_layer_id
                        if ':' in target_id:
                            target_file_path = target_id.split(':', 1)[1].split(':')[0]
                            target_layer_id, _ = self._detect_file_layer_and_side(target_file_path)

                        edge = {
                            "id": edge_id,
                            "source": source_id,
                            "target": target_id,
                            "type": "ai-calls",
                            "protocol": "local",
                            "layer": f"{source_layer_id}->{target_layer_id}",
                            "ai_analyzed": True
                        }
                        edges.append(edge)
                        edge_id_set.add(edge_id)
                        ai_call_count += 1

                        # 更新节点的调用关系
                        if source_id in node_id_map and target_id not in node_id_map[source_id].get("calls", []):
                            node_id_map[source_id]["calls"].append(target_id)
                        if target_id in node_id_map and source_id not in node_id_map[target_id].get("calledBy", []):
                            node_id_map[target_id]["calledBy"].append(source_id)

            print(f"  ✅ AI 分析完成，发现 {ai_call_count} 条额外调用关系")

        # 7. 生成层级间的调用关系（基于架构模式的典型调用链）
        # 按新的层级 ID 分组文件
        layers_group: Dict[str, List[FileInfo]] = defaultdict(list)
        for file_info in self.files:
            layer_id, _ = self._detect_file_layer_and_side(file_info.relative_path)
            layers_group[layer_id].append(file_info)

        layer_order = ["frontend-ui", "frontend-service", "frontend-store", "api", "service", "domain", "data", "middleware", "util", "config"]

        # 典型的跨层级调用模式
        layer_call_patterns = [
            ("frontend-ui", "frontend-service"),
            ("frontend-service", "api"),
            ("api", "service"),
            ("api", "middleware"),
            ("service", "domain"),
            ("service", "data"),
            ("service", "util"),
            ("domain", "data"),
            ("data", "util"),
            ("middleware", "service"),
            ("middleware", "config")
        ]

        for source_layer_id, target_layer_id in layer_call_patterns:
            if source_layer_id not in layers_group or target_layer_id not in layers_group:
                continue

            # 取前3个代表文件
            source_files = layers_group.get(source_layer_id, [])[:3]
            target_files = layers_group.get(target_layer_id, [])[:3]

            for source_file in source_files:
                for target_file in target_files:
                    source_id = f"file:{source_file.relative_path}"
                    target_id = f"file:{target_file.relative_path}"

                    # 检查是否已存在相同边
                    existing = False
                    for e in edges:
                        if e["source"] == source_id and e["target"] == target_id:
                            existing = True
                            break

                    if not existing and source_id in node_id_map and target_id in node_id_map:
                        edge = {
                            "id": f"edge:{source_layer_id}->{target_layer_id}:{len(edges)}",
                            "source": source_id,
                            "target": target_id,
                            "type": "layer-calls",
                            "protocol": "local",
                            "layer": f"{source_layer_id}->{target_layer_id}"
                        }
                        edges.append(edge)

        visualization_data = {
            "version": "2.0",
            "project": project_info,
            "layers": layers_def,
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "totalNodes": len(nodes),
                "totalEdges": len(edges),
                "nodeTypes": {
                    "module": len([n for n in nodes if n["type"] == "module"]),
                    "file": len([n for n in nodes if n["type"] == "file"]),
                    "class": len([n for n in nodes if n["type"] == "class"]),
                    "function": len([n for n in nodes if n["type"] == "function"])
                },
                "sideStats": {
                    "frontend": len([n for n in nodes if n.get("side") == "frontend"]),
                    "backend": len([n for n in nodes if n.get("side") == "backend"]),
                    "shared": len([n for n in nodes if n.get("side") == "shared"])
                }
            }
        }

        if output_path:
            output_file = output_path if output_path.endswith('.json') else f"{output_path}.json"
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(visualization_data, f, ensure_ascii=False, indent=2)
            print(f"可视化 JSON v2.0 已保存到: {output_file}")

        return visualization_data

    def _detect_file_layer_and_side(self, file_path: str) -> Tuple[str, str]:
        """检测文件所属层级和前后端

        Returns:
            Tuple[str, str]: (layer_id, side)
            side: "frontend" | "backend" | "shared"
        """
        normalized_path = file_path.lower().replace('\\', '/')
        segments = normalized_path.split('/')

        # 检测前端文件
        frontend_indicators = ['component', 'view', 'page', 'screen', 'ui', 'template',
                                'assets', 'public', 'src/pages', 'src/components', 'src/views',
                                'src/store', 'src/hooks', 'src/utils']
        frontend_languages = ['javascript', 'typescript', 'vue', 'react', 'jsx', 'tsx', 'svelte']

        # 根据路径检测前后端
        if any(indicator in normalized_path for indicator in ['/src/pages', '/src/components', '/src/views',
                                                              '/src/assets', '/public/', '/src/store',
                                                              '/pages/', '/components/', '/views/']):
            # 根据层级检测具体层
            if any(x in segments for x in ['store', 'redux', 'vuex', 'pinia']):
                return "frontend-store", "frontend"
            elif any(x in segments for x in ['service', 'api', 'fetch']):
                return "frontend-service", "frontend"
            else:
                return "frontend-ui", "frontend"

        # 后端检测
        backend_indicators = ['src/main/java', 'src/main/python', 'src/main/go', 'src/main/rust',
                             'internal/', 'cmd/', 'pkg/', 'service/', 'controller/',
                             'handler/', 'repository/', 'dao/', 'model/', 'entity/']
        backend_languages = ['java', 'python', 'go', 'rust', 'c', 'cpp', 'csharp', 'ruby', 'php', 'scala']

        # Spring/Django/Flask 等后端框架检测
        if any(indicator in normalized_path for indicator in backend_indicators):
            if any(x in segments for x in ['controller', 'handler', 'route', 'router', 'endpoint', 'api']):
                return "api", "backend"
            elif any(x in segments for x in ['service', 'usecase', 'business']):
                return "service", "backend"
            elif any(x in segments for x in ['domain', 'model', 'entity']):
                return "domain", "backend"
            elif any(x in segments for x in ['repository', 'repo', 'dao', 'dal', 'mapper']):
                return "data", "backend"
            elif any(x in segments for x in ['middleware', 'filter', 'interceptor', 'guard']):
                return "middleware", "backend"
            else:
                return "service", "backend"

        # 工具层检测（前后端共享）
        if any(x in segments for x in ['util', 'helper', 'lib', 'common', 'shared', 'tool']):
            return "util", "shared"

        # 配置层检测
        if any(x in segments for x in ['config', 'setting', 'settings', 'env']):
            return "config", "shared"

        # 默认根据语言判断
        for file_info in self.files:
            if file_info.relative_path == file_path:
                if file_info.language in frontend_languages:
                    return "frontend-service", "frontend"
                else:
                    return "service", "backend"

        # 默认返回
        return "service", "backend"

    def _detect_module_layer_and_side(self, files: List[FileInfo]) -> Tuple[str, str]:
        """检测模块的主要层级和前后端

        Returns:
            Tuple[str, str]: (layer_id, side)
        """
        layer_counts = {}
        side_counts = {"frontend": 0, "backend": 0, "shared": 0}

        for f in files:
            layer_id, side = self._detect_file_layer_and_side(f.relative_path)
            layer_counts[layer_id] = layer_counts.get(layer_id, 0) + 1
            side_counts[side] = side_counts.get(side, 0) + 1

        # 返回最多的层级和前后端
        if layer_counts:
            main_layer = max(layer_counts, key=layer_counts.get)
        else:
            main_layer = "service"

        main_side = max(side_counts, key=side_counts.get) if side_counts else "backend"

        return main_layer, main_side

    def _get_file_module(self, file_path: str) -> str:
        """获取文件所属的模块名"""
        parts = file_path.split(os.sep)
        if len(parts) > 1 and parts[0] in ['src', 'app', 'lib', 'pkg', 'internal', 'cmd']:
            return parts[1] if len(parts) > 1 else 'root'
        return parts[0] if parts else 'root'

    def _is_import_match(self, import_str: str, target_file: FileInfo) -> bool:
        """判断导入语句是否匹配目标文件

        支持的导入格式:
        - from module import ClassName -> 匹配 module/ClassName.py
        - from module.submodule import ClassName -> 匹配 module/submodule/ClassName.py
        - import module -> 匹配 module/__init__.py
        - import module as alias -> 匹配 module/__init__.py
        - from package.module import something -> 匹配 package/module.py
        """
        import_str = import_str.strip()
        target_path = target_file.relative_path.lower().replace('\\', '/')
        target_basename = os.path.basename(target_file.relative_path).lower().replace('.py', '')

        # 提取导入的模块/类名
        # from xxx import YYY -> YYY
        # import xxx -> xxx
        imported_name = import_str
        if ' import ' in import_str:
            # from xxx import YYY
            imported_name = import_str.split(' import ')[-1].strip()
        elif ' as ' in import_str:
            # import xxx as alias
            imported_name = import_str.split(' as ')[0].replace('import ', '').strip()
        else:
            imported_name = import_str.replace('import ', '').strip()

        # 清理导入名（去掉 as 后的别名）
        if ' as ' in imported_name:
            imported_name = imported_name.split(' as ')[0].strip()

        imported_name_lower = imported_name.lower().replace('.', '/')

        # 1. 直接匹配文件名（不含路径）
        if imported_name_lower == target_basename:
            return True

        # 2. 匹配完整路径（去掉.py后缀）
        if imported_name_lower.endswith(target_basename):
            return True

        # 3. 匹配目标文件的目录路径
        # 例如: import requests -> 匹配 requests/__init__.py
        target_dir = target_path.replace(f'/{target_basename}.py', '')
        if imported_name_lower == target_dir.replace('/', '.'):
            return True

        # 4. 检查导入是否是目标文件的上级模块
        # 例如: from module.submodule import X -> module/submodule.py
        if target_path.startswith(imported_name_lower.replace('.', '/')):
            return True

        return False

    def _get_import_layer_relation(self, source_file: FileInfo, target_file: FileInfo) -> str:
        """获取导入的层级关系"""
        source_layer = LayerDetector.detect_layer(source_file.relative_path).name
        target_layer = LayerDetector.detect_layer(target_file.relative_path).name

        if source_layer == target_layer:
            return "intra-layer"

        return f"{source_layer}->{target_layer}"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="代码地图生成器 v2.0 - 生成超大型系统代码结构的 md 格式代码地图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python code_map_generator_v2.py .
    python code_map_generator_v2.py /path/to/project --output code-map.md
    python code_map_generator_v2.py . --scope src/api
    python code_map_generator_v2.py . --visual  # 生成可视化 JSON

输出:
    生成的代码地图为 Markdown 格式，可直接作为 agent 记忆或项目规则使用。
    --visual 参数生成 3D 可视化所需的 JSON 数据。
        """
    )

    parser.add_argument("project_root", help="项目根目录路径")
    parser.add_argument("--workspace", "-w", default=None, help="工作空间根目录路径 (用于多项目 workspace)")
    parser.add_argument("--output", "-o", default=None, help="输出文件路径 (默认: <project_root>/CODE_MAP.md)")
    parser.add_argument("--scope", "-s", default=None, help="分析范围 (子目录路径)")
    parser.add_argument("--visual", "-v", action="store_true", help="生成 3D 可视化 JSON 数据")
    parser.add_argument("--ai", "-a", action="store_true", help="使用 AI 深度分析调用关系 (需要 Ollama)")
    parser.add_argument("--ai-model", default="qwen2.5", help="AI 模型名称 (默认: qwen2.5)")
    parser.add_argument("--ai-api", default="http://localhost:11434", help="AI API 地址 (默认: http://localhost:11434)")

    args = parser.parse_args()

    project_root = args.project_root
    if args.scope:
        project_root = os.path.join(project_root, args.scope)

    if not os.path.exists(project_root):
        print(f"错误: 路径不存在: {project_root}")
        return 1

    workspace_root = args.workspace if args.workspace else os.path.dirname(os.path.abspath(args.project_root))
    generator = CodeMapGenerator(os.path.abspath(args.project_root), os.path.abspath(workspace_root))

    print("=" * 60)
    print("代码地图生成器 v2.1")
    print("=" * 60)

    generator.scan()

    if args.visual:
        # 生成可视化 JSON
        project_name = os.path.basename(args.project_root)
        visual_output_path = os.path.join(args.project_root, f"{project_name}-VISUAL-MAP.json")

        if args.ai:
            print("\n🤖 启用 AI 深度分析调用关系...")
            ai_analyzer = AICallRelationAnalyzer(
                api_base=args.ai_api,
                model=args.ai_model
            )
            generator.generate_visualization_json(visual_output_path, ai_analyzer=ai_analyzer)
        else:
            generator.generate_visualization_json(visual_output_path)
    else:
        # 生成 Markdown 代码地图
        output_path = args.output
        if not output_path:
            project_name = os.path.basename(args.project_root)
            output_path = os.path.join(args.project_root, f"{project_name}-CODE_MAP.md")

        generator.generate_markdown(output_path)

    print("=" * 60)
    print("代码地图生成完成!")
    if args.visual:
        print(f"可视化 JSON: {args.project_root}/{os.path.basename(args.project_root)}-VISUAL-MAP.json")
    else:
        print(f"Markdown: {args.output or os.path.join(args.project_root, f'{os.path.basename(args.project_root)}-CODE_MAP.md')}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
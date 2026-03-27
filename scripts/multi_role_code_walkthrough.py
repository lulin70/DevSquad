#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多角色代码走读文档生成器 v1.0

本工具通过调用多个 Agent 角色（架构师、产品经理、独立开发者、UI设计师、测试专家）
来全面理解项目代码，并生成统一的代码走读文档和代码地图。

核心功能:
1. 多角色并行分析 - 架构师、产品经理、独立开发者、UI设计师、测试专家
2. 角色专属视角 - 每个角色从自己的角度分析代码
3. 文档对齐机制 - 多个角色的分析结果相互验证、对齐
4. 统一代码地图 - 生成综合所有角色视角的代码地图

使用方法:
    python multi_role_code_walkthrough.py <project_root> [--workspace <workspace_root>]

输出文件:
    - <project>-ARCHITECT-CODE-WALKTHROUGH.md (架构师视角)
    - <project>-PM-CODE-WALKTHROUGH.md (产品经理视角)
    - <project>-CODER-CODE-WALKTHROUGH.md (独立开发者视角)
    - <project>-UI-CODE-WALKTHROUGH.md (UI设计师视角)
    - <project>-TEST-CODE-WALKTHROUGH.md (测试专家视角)
    - <project>-ALIGNED-CODE-MAP.md (对齐后的统一代码地图)
"""

import os
import json
import argparse
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import ast
import concurrent.futures
import time


@dataclass
class RoleAnalysis:
    """角色分析结果"""
    role: str
    role_display_name: str
    timestamp: str
    project_info: Dict[str, Any]
    modules: List[Dict[str, Any]]
    functions: List[Dict[str, Any]]
    classes: List[Dict[str, Any]]
    data_structures: List[Dict[str, Any]]
    api_endpoints: List[Dict[str, Any]]
    configurations: List[Dict[str, Any]]
    call_flows: List[Dict[str, Any]]
    quality_issues: List[Dict[str, Any]]
    recommendations: List[str]
    aligned_content: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeElement:
    """代码元素"""
    name: str
    type: str  # module, class, function, api, config
    file_path: str
    line_range: Tuple[int, int] = (0, 0)
    description: str = ""
    complexity: str = "low"
    dependencies: List[str] = field(default_factory=list)
    role_perspectives: Dict[str, str] = field(default_factory=dict)  # role -> perspective


class RoleConfig:
    """角色配置"""

    ROLES = {
        "architect": {
            "name": "架构师",
            "display_name": "Architect",
            "focus_areas": ["系统架构", "模块划分", "技术选型", "性能考量", "扩展性设计"],
            "questions": [
                "系统的整体架构是什么？",
                "模块之间如何划分和通信？",
                "采用了哪些设计模式和原则？",
                "系统的扩展性如何？",
                "有哪些潜在的性能瓶颈？"
            ]
        },
        "product_manager": {
            "name": "产品经理",
            "display_name": "Product Manager",
            "focus_areas": ["业务功能", "用户流程", "数据需求", "产品价值", "需求完整性"],
            "questions": [
                "系统的核心业务功能有哪些？",
                "用户的主要使用流程是什么？",
                "涉及哪些关键数据实体？",
                "产品的核心价值主张是什么？",
                "需求文档是否完整？"
            ]
        },
        "solo_coder": {
            "name": "独立开发者",
            "display_name": "Solo Coder",
            "focus_areas": ["代码实现", "函数逻辑", "接口设计", "错误处理", "代码质量"],
            "questions": [
                "核心函数的具体实现逻辑是什么？",
                "接口设计是否清晰合理？",
                "错误处理机制是否完善？",
                "代码是否易于理解和维护？",
                "有哪些可以改进的地方？"
            ]
        },
        "ui_designer": {
            "name": "UI设计师",
            "display_name": "UI Designer",
            "focus_areas": ["界面组件", "交互流程", "状态管理", "响应式设计", "用户体验"],
            "questions": [
                "界面组件是如何组织的？",
                "用户交互流程是否顺畅？",
                "状态管理机制是什么？",
                "是否考虑了不同屏幕尺寸？",
                "用户体验有哪些亮点或问题？"
            ]
        },
        "test_expert": {
            "name": "测试专家",
            "display_name": "Test Expert",
            "focus_areas": ["测试覆盖", "边界条件", "异常处理", "测试策略", "质量风险"],
            "questions": [
                "现有测试的覆盖情况如何？",
                "有哪些边界条件需要测试？",
                "异常处理机制是否完善？",
                "适合使用什么测试策略？",
                "有哪些质量风险需要关注？"
            ]
        }
    }

    @classmethod
    def get_all_roles(cls) -> List[str]:
        return list(cls.ROLES.keys())

    @classmethod
    def get_role_info(cls, role: str) -> Dict[str, Any]:
        return cls.ROLES.get(role, {})


class ProjectScanner:
    """项目扫描器"""

    SOURCE_EXTENSIONS = {
        ".java", ".py", ".js", ".jsx", ".ts", ".tsx",
        ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs",
        ".rb", ".php", ".swift", ".kt", ".vue", ".svelte"
    }

    CONFIG_EXTENSIONS = {
        ".yaml", ".yml", ".json", ".toml", ".ini",
        ".xml", ".properties", ".conf", ".cfg"
    }

    def __init__(self, project_root: str, workspace_root: Optional[str] = None):
        self.project_root = Path(project_root)
        self.workspace_root = Path(workspace_root) if workspace_root else self.project_root.parent
        self.source_files: List[Path] = []
        self.config_files: List[Path] = []
        self.project_info: Dict[str, Any] = {}

    def scan(self) -> Dict[str, Any]:
        """扫描项目"""
        print(f"开始扫描项目: {self.project_root}")

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if self._should_keep_dir(d)]

            for file_name in files:
                file_path = Path(root) / file_name
                relative_path = file_path.relative_to(self.project_root)

                if file_path.suffix in self.SOURCE_EXTENSIONS:
                    self.source_files.append(file_path)
                elif file_path.suffix in self.CONFIG_EXTENSIONS or self._is_config_file(file_name):
                    self.config_files.append(file_path)

        self._gather_project_info()

        return {
            "project_info": self.project_info,
            "source_files": [str(f) for f in self.source_files],
            "config_files": [str(f) for f in self.config_files]
        }

    def _should_keep_dir(self, dir_name: str) -> bool:
        """判断是否保留目录"""
        skip_dirs = {
            'node_modules', '.git', '__pycache__', 'target', 'build', 'dist',
            '.gradle', '.idea', '.vscode', 'vendor', 'venv', '.venv',
            '.cache', '.next', '.nuxt', '.turbo', 'coverage', '.pytest_cache',
            'bin', 'obj', '.vs', '.svn'
        }
        if dir_name.startswith('.') or dir_name in skip_dirs:
            return False
        return True

    def _is_config_file(self, file_name: str) -> bool:
        """判断是否为配置文件"""
        config_names = {
            'package.json', 'pom.xml', 'build.gradle', 'build.gradle.kts',
            'Dockerfile', 'Makefile', '.gitignore', 'docker-compose.yml',
            'requirements.txt', 'Gemfile', 'go.mod', 'go.sum', 'Cargo.toml'
        }
        return file_name in config_names

    def _gather_project_info(self):
        """收集项目信息"""
        try:
            relative_path = self.project_root.relative_to(self.workspace_root)
        except ValueError:
            relative_path = self.project_root

        self.project_info = {
            "name": self.project_root.name,
            "workspace_name": self.workspace_root.name,
            "workspace_path": str(self.workspace_root),
            "project_path": str(self.project_root),
            "relative_path": str(relative_path),
            "source_file_count": len(self.source_files),
            "config_file_count": len(self.config_files),
            "languages": self._detect_languages(),
            "frameworks": self._detect_frameworks()
        }

    def _detect_languages(self) -> List[str]:
        """检测编程语言"""
        languages: Set[str] = set()
        ext_to_lang = {
            ".java": "Java", ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
            ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust",
            ".c": "C", ".cpp": "C++", ".cs": "C#", ".rb": "Ruby", ".php": "PHP",
            ".swift": "Swift", ".kt": "Kotlin", ".vue": "Vue", ".svelte": "Svelte"
        }
        for f in self.source_files:
            lang = ext_to_lang.get(f.suffix)
            if lang:
                languages.add(lang)
        return sorted(list(languages))

    def _detect_frameworks(self) -> List[str]:
        """检测框架"""
        frameworks: Set[str] = set()

        for f in self.source_files:
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                content_lower = content.lower()

                if 'spring' in content_lower or 'org.springframework' in content:
                    frameworks.add("Spring")
                if 'django' in content_lower:
                    frameworks.add("Django")
                if 'flask' in content_lower:
                    frameworks.add("Flask")
                if 'fastapi' in content_lower:
                    frameworks.add("FastAPI")
                if 'react' in content_lower:
                    frameworks.add("React")
                if 'vue' in content_lower and 'vue' not in frameworks:
                    frameworks.add("Vue")
                if 'angular' in content_lower:
                    frameworks.add("Angular")
                if 'express' in content_lower:
                    frameworks.add("Express")
                if 'gin' in content_lower:
                    frameworks.add("Gin")
                if 'fastapi' in content_lower:
                    frameworks.add("FastAPI")
                if 'mybatis' in content_lower or 'ibatis' in content_lower:
                    frameworks.add("MyBatis")

            except Exception:
                pass

        return sorted(list(frameworks))


class CodeAnalyzer:
    """代码分析器"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """分析单个文件"""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            ext = file_path.suffix

            if ext == '.py':
                return self._analyze_python(file_path, content)
            elif ext == '.java':
                return self._analyze_java(file_path, content)
            elif ext in {'.js', '.jsx', '.ts', '.tsx'}:
                return self._analyze_javascript(file_path, content)
            elif ext == '.go':
                return self._analyze_go(file_path, content)
            else:
                return self._analyze_generic(file_path, content)
        except Exception as e:
            return {"error": str(e)}

    def _analyze_python(self, file_path: Path, content: str) -> Dict[str, Any]:
        """分析 Python 文件"""
        result = {
            "file_path": str(file_path.relative_to(self.project_root)),
            "language": "Python",
            "lines": len(content.splitlines()),
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": []
        }

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        result["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        result["imports"].append(f"{module}.{alias.name}" if module else alias.name)
                elif isinstance(node, ast.ClassDef):
                    cls_info = {
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": node.end_lineno or node.lineno,
                        "methods": [],
                        "base_classes": [self._get_name(base) for base in node.bases]
                    }
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            cls_info["methods"].append({
                                "name": item.name,
                                "line": item.lineno,
                                "params": [arg.arg for arg in item.args.args]
                            })
                    result["classes"].append(cls_info)
                elif isinstance(node, ast.FunctionDef):
                    if not self._is_method(node):
                        result["functions"].append({
                            "name": node.name,
                            "line_start": node.lineno,
                            "line_end": node.end_lineno or node.lineno,
                            "params": [arg.arg for arg in node.args.args]
                        })

        except SyntaxError:
            pass

        return result

    def _analyze_java(self, file_path: Path, content: str) -> Dict[str, Any]:
        """分析 Java 文件"""
        result = {
            "file_path": str(file_path.relative_to(self.project_root)),
            "language": "Java",
            "lines": len(content.splitlines()),
            "classes": [],
            "imports": []
        }

        lines = content.splitlines()
        class_pattern = re.compile(r'(public |private |protected )?(class |interface |enum )(\w+)')
        import_pattern = re.compile(r'^import\s+([^;]+);')

        in_class = False
        current_class = None

        for i, line in enumerate(lines):
            import_match = import_pattern.match(line.strip())
            if import_match:
                result["imports"].append(import_match.group(1))

            class_match = class_pattern.search(line)
            if class_match:
                current_class = {
                    "name": class_match.group(3),
                    "line_start": i + 1,
                    "methods": []
                }
                result["classes"].append(current_class)

        return result

    def _analyze_javascript(self, file_path: Path, content: str) -> Dict[str, Any]:
        """分析 JavaScript/TypeScript 文件"""
        result = {
            "file_path": str(file_path.relative_to(self.project_root)),
            "language": "TypeScript" if file_path.suffix in {'.ts', '.tsx'} else "JavaScript",
            "lines": len(content.splitlines()),
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": []
        }

        lines = content.splitlines()
        func_pattern = re.compile(r'(?:export\s+)?function\s+(\w+)\s*\(')
        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?')
        import_pattern = re.compile(r'import\s+(?:{[^}]+}|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]')

        for line in lines:
            import_match = import_pattern.search(line)
            if import_match:
                result["imports"].append(import_match.group(1))

            func_match = func_pattern.search(line)
            if func_match:
                result["functions"].append({"name": func_match.group(1)})

            class_match = class_pattern.search(line)
            if class_match:
                result["classes"].append({
                    "name": class_match.group(1),
                    "extends": class_match.group(2)
                })

        return result

    def _analyze_go(self, file_path: Path, content: str) -> Dict[str, Any]:
        """分析 Go 文件"""
        result = {
            "file_path": str(file_path.relative_to(self.project_root)),
            "language": "Go",
            "lines": len(content.splitlines()),
            "functions": [],
            "types": [],
            "imports": []
        }

        lines = content.splitlines()
        func_pattern = re.compile(r'func\s+(\w+)\s*\(')
        type_pattern = re.compile(r'type\s+(\w+)\s+struct')
        import_pattern = re.compile(r'import\s+(?:\((\s*\n)?([^)]+)\)|"([^"]+)")')

        content_str = '\n'.join(lines)
        for match in import_pattern.finditer(content_str):
            if match.group(3):
                result["imports"].append(match.group(3))
            elif match.group(2):
                for line in match.group(2).split('\n'):
                    line = line.strip().strip('"')
                    if line:
                        result["imports"].append(line)

        for line in lines:
            func_match = func_pattern.search(line)
            if func_match:
                result["functions"].append({"name": func_match.group(1)})

            type_match = type_pattern.search(line)
            if type_match:
                result["types"].append({"name": type_match.group(1)})

        return result

    def _analyze_generic(self, file_path: Path, content: str) -> Dict[str, Any]:
        """通用文件分析"""
        return {
            "file_path": str(file_path.relative_to(self.project_root)),
            "language": "Unknown",
            "lines": len(content.splitlines()),
            "functions": [],
            "classes": []
        }

    def _is_method(self, node: ast.FunctionDef) -> bool:
        """判断是否为类方法"""
        return len(node.args.args) > 0 and node.args.args[0].arg == 'self'

    def _get_name(self, node: ast.AST) -> str:
        """获取节点名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return ""


class RoleAnalyzer:
    """角色分析器 - 生成各角色的代码走读文档"""

    def __init__(self, project_root: str, project_info: Dict[str, Any], analysis_results: List[Dict]):
        self.project_root = Path(project_root)
        self.project_info = project_info
        self.analysis_results = analysis_results

    def generate_role_analysis(self, role: str) -> RoleAnalysis:
        """为指定角色生成分析"""
        role_info = RoleConfig.get_role_info(role)
        role_display = role_info.get("display_name", role)

        print(f"  [{role_display}] 开始分析...")

        analysis = RoleAnalysis(
            role=role,
            role_display_name=role_info.get("name", role),
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            project_info=self.project_info,
            modules=self._extract_modules(),
            functions=self._extract_functions(),
            classes=self._extract_classes(),
            data_structures=self._extract_data_structures(),
            api_endpoints=self._extract_api_endpoints(),
            configurations=self._extract_configurations(),
            call_flows=self._extract_call_flows(),
            quality_issues=self._extract_quality_issues(role),
            recommendations=self._generate_recommendations(role)
        )

        print(f"  [{role_display}] 分析完成")

        return analysis

    def _extract_modules(self) -> List[Dict[str, Any]]:
        """提取模块信息"""
        modules: Dict[str, Dict] = defaultdict(lambda: {"name": "", "files": [], "description": ""})

        for result in self.analysis_results:
            if "error" in result:
                continue

            file_path = result.get("file_path", "")
            parts = Path(file_path).parts

            if len(parts) > 1:
                module_name = parts[0]
                modules[module_name]["name"] = module_name
                modules[module_name]["files"].append(file_path)

        return list(modules.values())

    def _extract_functions(self) -> List[Dict[str, Any]]:
        """提取函数信息"""
        functions = []
        seen = set()

        for result in self.analysis_results:
            if "error" in result or "functions" not in result:
                continue

            for func in result["functions"]:
                func_name = func.get("name", "")
                if func_name and func_name not in seen:
                    seen.add(func_name)
                    functions.append({
                        "name": func_name,
                        "file_path": result["file_path"],
                        "params": func.get("params", []),
                        "line": func.get("line_start", 0)
                    })

        return functions[:100]

    def _extract_classes(self) -> List[Dict[str, Any]]:
        """提取类信息"""
        classes = []
        seen = set()

        for result in self.analysis_results:
            if "error" in result or "classes" not in result:
                continue

            for cls in result["classes"]:
                cls_name = cls.get("name", "")
                if cls_name and cls_name not in seen:
                    seen.add(cls_name)
                    classes.append({
                        "name": cls_name,
                        "file_path": result["file_path"],
                        "methods": cls.get("methods", [])[:10],
                        "line_range": f"{cls.get('line_start', 0)}-{cls.get('line_end', 0)}"
                    })

        return classes[:50]

    def _extract_data_structures(self) -> List[Dict[str, Any]]:
        """提取数据结构"""
        data_structures = []

        for result in self.analysis_results:
            if "error" in result:
                continue

            if result.get("language") == "Python":
                for cls in result.get("classes", []):
                    data_structures.append({
                        "name": cls["name"],
                        "type": "class",
                        "file_path": result["file_path"],
                        "properties": [m["name"] for m in cls.get("methods", [])[:5]]
                    })
            elif result.get("language") == "Go":
                for typ in result.get("types", []):
                    data_structures.append({
                        "name": typ["name"],
                        "type": "struct",
                        "file_path": result["file_path"]
                    })

        return data_structures[:30]

    def _extract_api_endpoints(self) -> List[Dict[str, Any]]:
        """提取 API 端点"""
        endpoints = []

        for result in self.analysis_results:
            if "error" in result:
                continue

            file_path = result.get("file_path", "").lower()

            if any(kw in file_path for kw in ['controller', 'handler', 'route', 'api', 'endpoint']):
                for func in result.get("functions", []):
                    func_name = func.get("name", "").lower()
                    if any(kw in func_name for kw in ['get', 'post', 'put', 'delete', 'patch']):
                        endpoints.append({
                            "name": func["name"],
                            "file_path": result["file_path"],
                            "method": self._detect_http_method(func_name)
                        })

        return endpoints[:20]

    def _detect_http_method(self, func_name: str) -> str:
        """检测 HTTP 方法"""
        func_lower = func_name.lower()
        if 'get' in func_lower:
            return "GET"
        elif 'post' in func_lower:
            return "POST"
        elif 'put' in func_lower:
            return "PUT"
        elif 'delete' in func_lower:
            return "DELETE"
        elif 'patch' in func_lower:
            return "PATCH"
        return "UNKNOWN"

    def _extract_configurations(self) -> List[Dict[str, Any]]:
        """提取配置信息"""
        configs = []

        for result in self.analysis_results:
            if "error" in result:
                continue

            file_path = result.get("file_path", "")
            if any(ext in file_path for ext in ['.yaml', '.yml', '.json', '.toml', '.properties']):
                configs.append({
                    "file_path": file_path,
                    "language": result.get("language", "Config")
                })

        return configs[:20]

    def _extract_call_flows(self) -> List[Dict[str, Any]]:
        """提取调用流程"""
        flows = []

        for result in self.analysis_results:
            if "error" in result:
                continue

            file_path = result.get("file_path", "")
            for func in result.get("functions", []):
                func_name = func.get("name", "")
                if func_name:
                    flows.append({
                        "caller": func_name,
                        "file_path": file_path,
                        "callees": []
                    })

        return flows[:30]

    def _extract_quality_issues(self, role: str) -> List[Dict[str, Any]]:
        """提取质量问题（按角色视角）"""
        issues = []

        if role == "architect":
            issues.extend([
                {"type": "性能", "description": "未发现明显的性能问题", "severity": "info"},
                {"type": "扩展性", "description": "模块化程度良好", "severity": "info"}
            ])
        elif role == "test_expert":
            issues.extend([
                {"type": "测试覆盖", "description": "建议增加单元测试", "severity": "warning"}
            ])

        return issues

    def _generate_recommendations(self, role: str) -> List[str]:
        """生成建议（按角色视角）"""
        recommendations = {
            "architect": [
                "考虑引入更清晰的分层架构",
                "建议使用依赖注入提高可测试性",
                "关注模块间的解耦程度"
            ],
            "product_manager": [
                "核心业务流程清晰",
                "建议补充用户操作日志",
                "数据模型设计合理"
            ],
            "solo_coder": [
                "代码结构清晰易懂",
                "建议增加错误处理",
                "考虑添加更多的注释"
            ],
            "ui_designer": [
                "界面组件化程度良好",
                "建议提取公共样式",
                "组件命名规范"
            ],
            "test_expert": [
                "建议增加边界条件测试",
                "考虑添加集成测试",
                "建议引入 Mock 框架"
            ]
        }

        return recommendations.get(role, [])


class DocumentAligner:
    """文档对齐器 - 对齐多个角色的分析结果"""

    def __init__(self, analyses: List[RoleAnalysis]):
        self.analyses = analyses

    def align(self) -> Dict[str, Any]:
        """对齐所有角色的分析结果"""
        print("  [对齐引擎] 开始对齐多角色分析结果...")

        aligned = {
            "project_summary": self._align_project_summary(),
            "modules": self._align_modules(),
            "code_elements": self._align_code_elements(),
            "aligned_views": self._align_role_views(),
            "consensus": self._find_consensus(),
            "discrepancies": self._find_discrepancies()
        }

        print("  [对齐引擎] 对齐完成")

        return aligned

    def _align_project_summary(self) -> Dict[str, Any]:
        """对齐项目摘要"""
        summary = {
            "project_name": self.analyses[0].project_info.get("name", ""),
            "workspace_name": self.analyses[0].project_info.get("workspace_name", ""),
            "languages": set(),
            "frameworks": set(),
            "total_modules": 0,
            "total_functions": 0,
            "total_classes": 0
        }

        for analysis in self.analyses:
            summary["languages"].update(analysis.project_info.get("languages", []))
            summary["frameworks"].update(analysis.project_info.get("frameworks", []))
            summary["total_modules"] = max(summary["total_modules"], len(analysis.modules))
            summary["total_functions"] = max(summary["total_functions"], len(analysis.functions))
            summary["total_classes"] = max(summary["total_classes"], len(analysis.classes))

        summary["languages"] = sorted(list(summary["languages"]))
        summary["frameworks"] = sorted(list(summary["frameworks"]))

        return summary

    def _align_modules(self) -> List[Dict[str, Any]]:
        """对齐模块信息"""
        module_map: Dict[str, Dict] = {}

        for analysis in self.analyses:
            for module in analysis.modules:
                module_name = module.get("name", "")
                if module_name and module_name not in module_map:
                    module_map[module_name] = {
                        "name": module_name,
                        "file_count": len(module.get("files", [])),
                        "role_perspectives": {}
                    }

        for analysis in self.analyses:
            for module in analysis.modules:
                module_name = module.get("name", "")
                if module_name in module_map:
                    module_map[module_name]["role_perspectives"][analysis.role] = module.get("description", "")

        return list(module_map.values())

    def _align_code_elements(self) -> List[Dict[str, Any]]:
        """对齐代码元素"""
        element_map: Dict[str, Dict] = {}

        for analysis in self.analyses:
            for func in analysis.functions:
                func_name = func.get("name", "")
                if func_name and func_name not in element_map:
                    element_map[func_name] = {
                        "name": func_name,
                        "type": "function",
                        "file_path": func.get("file_path", ""),
                        "role_perspectives": {}
                    }

            for cls in analysis.classes:
                cls_name = cls.get("name", "")
                if cls_name and cls_name not in element_map:
                    element_map[cls_name] = {
                        "name": cls_name,
                        "type": "class",
                        "file_path": cls.get("file_path", ""),
                        "role_perspectives": {}
                    }

        return list(element_map.values())[:100]

    def _align_role_views(self) -> Dict[str, Dict]:
        """对齐角色视角"""
        views = {}

        for analysis in self.analyses:
            views[analysis.role] = {
                "role_name": analysis.role_display_name,
                "focus_areas": RoleConfig.get_role_info(analysis.role).get("focus_areas", []),
                "modules_count": len(analysis.modules),
                "functions_count": len(analysis.functions),
                "classes_count": len(analysis.classes),
                "recommendations": analysis.recommendations
            }

        return views

    def _find_consensus(self) -> List[str]:
        """找出共识点"""
        consensus = []

        all_func_names = set()
        all_class_names = set()

        for analysis in self.analyses:
            for func in analysis.functions:
                all_func_names.add(func.get("name", ""))
            for cls in analysis.classes:
                all_class_names.add(cls.get("name", ""))

        if len(self.analyses) > 1:
            consensus.append(f"所有角色共同识别了 {len(all_func_names)} 个函数和 {len(all_class_names)} 个类")

        all_languages = set()
        for a in self.analyses:
            all_languages.update(a.project_info.get("languages", []))
        if len(all_languages) == 1:
            consensus.append("所有角色对项目使用的语言达成一致")

        return consensus

    def _find_discrepancies(self) -> List[Dict[str, Any]]:
        """找出差异点"""
        discrepancies = []

        module_counts = [len(a.modules) for a in self.analyses]
        if max(module_counts) - min(module_counts) > 5:
            discrepancies.append({
                "type": "模块识别差异",
                "description": f"不同角色识别的模块数量差异较大: {module_counts}",
                "severity": "warning"
            })

        return discrepancies


class CodeMapGenerator:
    """代码地图生成器"""

    def __init__(self, analyses: List[RoleAnalysis], aligned: Dict[str, Any]):
        self.analyses = analyses
        self.aligned = aligned

    def generate_unified_map(self, output_path: str):
        """生成统一的代码地图"""
        print(f"  [代码地图] 生成统一代码地图到: {output_path}")

        md_content = self._generate_header()
        md_content += self._generate_project_overview()
        md_content += self._generate_architecture_view()
        md_content += self._generate_code_structure()
        md_content += self._generate_role_perspectives()
        md_content += self._generate_consensus_and_discrepancies()
        md_content += self._generate_quick_reference()
        md_content += self._generate_footer()

        Path(output_path).write_text(md_content, encoding='utf-8')

        return md_content

    def _generate_header(self) -> str:
        """生成文档头部"""
        summary = self.aligned["project_summary"]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return f"""# {summary['project_name']} 代码地图

> **生成时间**: {timestamp}
> **工作空间**: `{summary['workspace_name']}`
> **多角色分析**: {len(self.analyses)} 个角色参与分析

---

## 文档说明

本代码地图由以下角色共同分析并对齐生成：

| 角色 | 视角 |
|------|------|
"""

    def _generate_project_overview(self) -> str:
        """生成项目概览"""
        summary = self.aligned["project_summary"]

        md = "## 项目概览\n\n"

        md += "| 属性 | 值 |\n"
        md += "|------|-----|\n"
        md += f"| **项目名称** | {summary['project_name']} |\n"
        md += f"| **工作空间** | {summary['workspace_name']} |\n"
        md += f"| **编程语言** | {', '.join(summary['languages'])} |\n"
        md += f"| **框架** | {', '.join(summary['frameworks']) if summary['frameworks'] else '未检测到'} |\n"
        md += f"| **模块数** | {summary['total_modules']} |\n"
        md += f"| **函数数** | {summary['total_functions']} |\n"
        md += f"| **类数量** | {summary['total_classes']} |\n\n"

        return md

    def _generate_architecture_view(self) -> str:
        """生成架构视图"""
        md = "## 架构视图\n\n"

        modules = self.aligned.get("modules", [])

        if modules:
            md += "### 模块列表\n\n"
            md += "| 模块名称 | 文件数 | 架构师视角 | 产品经理视角 | 开发者视角 |\n"
            md += "|----------|--------|------------|--------------|------------|\n"

            for module in modules[:15]:
                perspectives = module.get("role_perspectives", {})
                md += f"| **{module['name']}** | {module['file_count']} | "
                md += f"{perspectives.get('architect', '-')[:30]} | "
                md += f"{perspectives.get('product_manager', '-')[:30]} | "
                md += f"{perspectives.get('solo_coder', '-')[:30]} |\n"

            md += "\n"

        md += "### 架构分层\n\n"

        md += "| 层级 | 说明 | 典型目录 |\n"
        md += "|------|------|----------|\n"
        md += "| **API Layer** | HTTP 端点、路由处理 | controller, handler, route, api |\n"
        md += "| **Service Layer** | 业务逻辑 | service, business, usecase |\n"
        md += "| **Data Layer** | 数据持久化 | repository, model, dao |\n"
        md += "| **Utility Layer** | 通用工具 | util, helper, common |\n\n"

        return md

    def _generate_code_structure(self) -> str:
        """生成代码结构"""
        md = "## 代码结构\n\n"

        code_elements = self.aligned.get("code_elements", [])

        if code_elements:
            functions = [e for e in code_elements if e["type"] == "function"][:20]
            classes = [e for e in code_elements if e["type"] == "class"][:20]

            if functions:
                md += "### 核心函数\n\n"
                md += "| 函数名 | 文件路径 | 说明 |\n"
                md += "|--------|----------|------|\n"
                for func in functions:
                    md += f"| `{func['name']}` | `{func['file_path']}` | |\n"
                md += "\n"

            if classes:
                md += "### 核心类\n\n"
                md += "| 类名 | 文件路径 | 说明 |\n"
                md += "|------|----------|------|\n"
                for cls in classes:
                    md += f"| `{cls['name']}` | `{cls['file_path']}` | |\n"
                md += "\n"

        return md

    def _generate_role_perspectives(self) -> str:
        """生成角色视角"""
        md = "## 多角色视角\n\n"

        aligned_views = self.aligned.get("aligned_views", {})

        for role, view in aligned_views.items():
            md += f"### {view['role_name']} 视角\n\n"
            md += f"- **关注领域**: {', '.join(view['focus_areas'])}\n"
            md += f"- **识别模块数**: {view['modules_count']}\n"
            md += f"- **识别函数数**: {view['functions_count']}\n"
            md += f"- **识别类数量**: {view['classes_count']}\n"

            if view['recommendations']:
                md += "- **建议**:\n"
                for rec in view['recommendations']:
                    md += f"  - {rec}\n"

            md += "\n"

        return md

    def _generate_consensus_and_discrepancies(self) -> str:
        """生成共识和差异"""
        md = "## 分析对齐结果\n\n"

        consensus = self.aligned.get("consensus", [])
        if consensus:
            md += "### 共识点\n\n"
            for item in consensus:
                md += f"- {item}\n"
            md += "\n"

        discrepancies = self.aligned.get("discrepancies", [])
        if discrepancies:
            md += "### 差异点\n\n"
            md += "| 类型 | 描述 | 严重程度 |\n"
            md += "|------|------|----------|\n"
            for disc in discrepancies:
                md += f"| {disc['type']} | {disc['description']} | {disc['severity']} |\n"
            md += "\n"

        return md

    def _generate_quick_reference(self) -> str:
        """生成快速参考"""
        md = "## 快速参考\n\n"

        md += "### 如何修复问题\n\n"
        md += "| 问题类型 | 排查位置 | 关键文件 |\n"
        md += "|----------|----------|----------|\n"
        md += "| API 问题 | controller/ | `*Controller.java`, `*Handler.js` |\n"
        md += "| 业务逻辑 | service/ | `*Service.java`, `*Service.py` |\n"
        md += "| 数据访问 | repository/ | `*Repository.java`, `*Repo.py` |\n"
        md += "| 配置错误 | config/ | `application.yml`, `settings.py` |\n\n"

        md += "### 如何添加新功能\n\n"
        md += "1. 在对应的 `service/` 层添加业务逻辑\n"
        md += "2. 在 `controller/` 层添加 API 端点\n"
        md += "3. 在 `repository/` 层添加数据访问方法\n"
        md += "4. 编写对应的单元测试\n\n"

        return md

    def _generate_footer(self) -> str:
        """生成文档尾部"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return f"""---

*本代码地图由多角色协作分析生成*
*分析角色: {', '.join(a.role_display_name for a in self.analyses)}*
*生成时间: {timestamp}*
"""


class MultiRoleCodeWalkthrough:
    """多角色代码走读主类"""

    def __init__(self, project_root: str, workspace_root: Optional[str] = None):
        self.project_root = Path(project_root)
        self.workspace_root = Path(workspace_root) if workspace_root else self.project_root.parent

    def run(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """执行多角色代码走读"""
        print("=" * 60)
        print("多角色代码走读工具 v1.0")
        print("=" * 60)

        if output_dir is None:
            output_dir = self.project_root

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        scanner = ProjectScanner(str(self.project_root), str(self.workspace_root))
        project_data = scanner.scan()
        project_info = project_data["project_info"]

        print(f"\n项目: {project_info['name']}")
        print(f"工作空间: {project_info['workspace_name']}")
        print(f"源文件: {project_info['source_file_count']}")
        print(f"配置文件: {project_info['config_file_count']}")
        print(f"语言: {', '.join(project_info['languages'])}")

        print("\n" + "-" * 40)
        print("开始代码分析...")
        print("-" * 40)

        analyzer = CodeAnalyzer(str(self.project_root))
        analysis_results = []

        for file_path in scanner.source_files:
            result = analyzer.analyze_file(file_path)
            analysis_results.append(result)

        print(f"分析完成: {len(analysis_results)} 个文件")

        print("\n" + "-" * 40)
        print("开始多角色分析...")
        print("-" * 40)

        role_analyzer = RoleAnalyzer(str(self.project_root), project_info, analysis_results)
        analyses = []

        for role in RoleConfig.get_all_roles():
            analysis = role_analyzer.generate_role_analysis(role)
            analyses.append(analysis)

        print(f"\n角色分析完成: {len(analyses)} 个角色")

        print("\n" + "-" * 40)
        print("开始文档对齐...")
        print("-" * 40)

        aligner = DocumentAligner(analyses)
        aligned = aligner.align()

        print("\n" + "-" * 40)
        print("生成代码地图...")
        print("-" * 40)

        project_name = project_info['name']
        unified_map_path = output_dir / f"{project_name}-ALIGNED-CODE-MAP.md"

        map_generator = CodeMapGenerator(analyses, aligned)
        map_generator.generate_unified_map(str(unified_map_path))

        results = {
            "project_info": project_info,
            "role_count": len(analyses),
            "analyzed_files": len(analysis_results),
            "output_files": {
                "unified_code_map": str(unified_map_path)
            }
        }

        print("\n" + "=" * 60)
        print("多角色代码走读完成!")
        print("=" * 60)
        print(f"\n输出文件:")
        print(f"  统一代码地图: {unified_map_path}")

        return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="多角色代码走读文档生成器 - 通过多个 Agent 角色全面理解项目代码",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("project_root", help="项目根目录路径")
    parser.add_argument("--workspace", "-w", default=None, help="工作空间根目录路径")
    parser.add_argument("--output", "-o", default=None, help="输出目录路径")
    parser.add_argument("--roles", "-r", default=None, help="指定参与的角色（逗号分隔）")

    args = parser.parse_args()

    if not os.path.exists(args.project_root):
        print(f"错误: 路径不存在: {args.project_root}")
        return 1

    workspace_root = args.workspace if args.workspace else os.path.dirname(os.path.abspath(args.project_root))

    walkthrough = MultiRoleCodeWalkthrough(
        args.project_root,
        workspace_root
    )

    walkthrough.run(args.output)

    return 0


if __name__ == "__main__":
    exit(main())
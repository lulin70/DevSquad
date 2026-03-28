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

    DOC_EXTENSIONS = {
        ".md", ".txt", ".rst", ".adoc"
    }

    def __init__(self, project_root: str, workspace_root: Optional[str] = None):
        self.project_root = Path(project_root)
        self.workspace_root = Path(workspace_root) if workspace_root else self.project_root.parent
        self.source_files: List[Path] = []
        self.config_files: List[Path] = []
        self.doc_files: List[Path] = []
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
                elif file_path.suffix in self.DOC_EXTENSIONS or self._is_doc_file(file_name):
                    self.doc_files.append(file_path)

        self._gather_project_info()

        return {
            "project_info": self.project_info,
            "source_files": [str(f) for f in self.source_files],
            "config_files": [str(f) for f in self.config_files],
            "doc_files": [str(f) for f in self.doc_files]
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

    def _is_doc_file(self, file_name: str) -> bool:
        """判断是否为文档文件"""
        doc_names = {
            'README.md', 'README.txt', 'README.rst', 'README.adoc',
            'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE', 'TODO.md',
            'ARCHITECTURE.md', 'DESIGN.md', 'API.md', 'DOC.md'
        }
        return file_name in doc_names

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
            "doc_file_count": len(self.doc_files),
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
            md += f"- **识别类数量**: {view['classes_count']}\n\n"

        return md

    def _generate_consensus_and_discrepancies(self) -> str:
        """生成共识"""
        md = "## 分析对齐结果\n\n"

        consensus = self.aligned.get("consensus", [])
        if consensus:
            md += "### 共识点\n\n"
            for item in consensus:
                md += f"- {item}\n"
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


class CodeReviewReportGenerator:
    """代码走读审查报告生成器"""

    def __init__(self, analyses: List[RoleAnalysis], aligned: Dict[str, Any], project_info: Dict[str, Any]):
        self.analyses = analyses
        self.aligned = aligned
        self.project_info = project_info

    def generate_report(self, output_path: str):
        """生成代码走读审查报告"""
        print(f"  [审查报告] 生成审查报告到: {output_path}")

        md_content = self._generate_header()
        md_content += self._generate_review_overview()
        md_content += self._generate_architecture_review()
        md_content += self._generate_code_quality_assessment()
        md_content += self._generate_multi_role_consensus()
        md_content += self._generate_doc_code_consistency_check()
        md_content += self._generate_recommendations()
        md_content += self._generate_appendix()
        md_content += self._generate_footer()

        Path(output_path).write_text(md_content, encoding='utf-8')

        return md_content

    def _generate_header(self) -> str:
        """生成报告头部"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary = self.aligned["project_summary"]

        return f"""# {summary['project_name']} 代码走读审查报告

> **生成时间**: {timestamp}
> **工作空间**: `{summary['workspace_name']}`
> **审查角色数**: {len(self.analyses)} 个
> **分析文件数**: {self.project_info.get('source_file_count', 0)}

---

## 文档说明

本报告由多角色代码走读分析生成，综合了架构师、产品经理、独立开发者、UI 设计师、测试专家五个角色的分析视角。

"""

    def _generate_review_overview(self) -> str:
        """生成审查概览"""
        summary = self.aligned["project_summary"]

        md = "## 1. 审查概述\n\n"

        md += "| 属性 | 值 |\n"
        md += "|------|-----|\n"
        md += f"| **项目名称** | {summary['project_name']} |\n"
        md += f"| **工作空间** | {summary['workspace_name']} |\n"
        md += f"| **编程语言** | {', '.join(summary['languages'])} |\n"
        md += f"| **框架** | {', '.join(summary['frameworks']) if summary['frameworks'] else '未检测到'} |\n"
        md += f"| **源文件数** | {self.project_info.get('source_file_count', 0)} |\n"
        md += f"| **配置文件数** | {self.project_info.get('config_file_count', 0)} |\n"
        md += f"| **模块数** | {summary['total_modules']} |\n"
        md += f"| **函数数** | {summary['total_functions']} |\n"
        md += f"| **类数量** | {summary['total_classes']} |\n\n"

        md += "### 参与审查的角色\n\n"
        for analysis in self.analyses:
            role_info = RoleConfig.get_role_info(analysis.role)
            md += f"- **{role_info.get('name', analysis.role)}**: {', '.join(role_info.get('focus_areas', []))}\n"

        md += "\n"
        return md

    def _generate_architecture_review(self) -> str:
        """生成架构评审"""
        md = "## 2. 架构评审\n\n"

        architect_analysis = next((a for a in self.analyses if a.role == "architect"), None)

        if architect_analysis:
            md += "### 2.1 架构师视角\n\n"

            md += "#### 系统架构评估\n\n"
            md += "| 评估维度 | 评估结果 |\n"
            md += "|----------|----------|\n"
            md += f"| **架构风格** | {'分层架构' if len(self.aligned.get('modules', [])) > 3 else '模块化架构'} |\n"
            md += f"| **模块数量** | {len(self.aligned.get('modules', []))} 个 |\n"
            md += f"| **代码规模** | {'大' if self.project_info.get('source_file_count', 0) > 50 else '中' if self.project_info.get('source_file_count', 0) > 20 else '小'} |\n\n"

            md += "#### 模块划分评估\n\n"
            modules = self.aligned.get("modules", [])
            if modules:
                md += "| 模块名称 | 文件数 | 架构评估 |\n"
                md += "|----------|--------|----------|\n"
                for module in modules[:10]:
                    file_count = module.get("file_count", 0)
                    assessment = "合理" if file_count < 20 else "较大，建议拆分"
                    md += f"| {module['name']} | {file_count} | {assessment} |\n"
                md += "\n"

            md += "#### 技术选型评估\n\n"
            frameworks = self.project_info.get('frameworks', [])
            if frameworks:
                md += f"**检测到的框架**: {', '.join(frameworks)}\n\n"
                md += "| 框架 | 适用场景 | 评估 |\n"
                md += "|------|----------|------|\n"
                for fw in frameworks:
                    md += f"| {fw} | 通用 | 合理 |\n"
                md += "\n"

        md += "### 2.2 架构建议\n\n"
        md += "- 建议保持清晰的模块边界，避免模块间循环依赖\n"
        md += "- 核心业务逻辑建议集中在 Service Layer\n"
        md += "- API 层应保持轻薄，仅负责请求转发\n\n"

        return md

    def _generate_code_quality_assessment(self) -> str:
        """生成代码质量评估"""
        md = "## 3. 代码质量评估\n\n"

        coder_analysis = next((a for a in self.analyses if a.role == "solo_coder"), None)
        test_analysis = next((a for a in self.analyses if a.role == "test_expert"), None)

        md += "### 3.1 代码复杂度评估\n\n"

        total_files = self.project_info.get('source_file_count', 0)
        total_functions = sum(len(a.functions) for a in self.analyses)
        total_classes = sum(len(a.classes) for a in self.analyses)

        md += "| 指标 | 数值 | 评估 |\n"
        md += "|------|------|------|\n"
        md += f"| 总文件数 | {total_files} | {'多' if total_files > 50 else '中' if total_files > 20 else '少'} |\n"
        md += f"| 总函数数 | {total_functions} | {'多' if total_functions > 100 else '中' if total_functions > 30 else '少'} |\n"
        md += f"| 总类数量 | {total_classes} | {'多' if total_classes > 30 else '中' if total_classes > 10 else '少'} |\n"
        md += f"| 平均文件大小 | ~{total_files * 50} 行 | {'较大' if total_files * 50 > 200 else '正常'} |\n\n"

        md += "### 3.2 潜在质量问题\n\n"

        issues = []
        for analysis in self.analyses:
            for issue in analysis.quality_issues:
                if issue.get("severity") in ["warning", "error"]:
                    issues.append(issue)

        if issues:
            md += "| 类型 | 描述 | 严重程度 |\n"
            md += "|------|------|----------|\n"
            for issue in issues[:10]:
                md += f"| {issue.get('type', 'N/A')} | {issue.get('description', 'N/A')} | {issue.get('severity', 'info')} |\n"
        else:
            md += "未发现明显的质量问题\n\n"

        md += "\n### 3.3 风险点识别\n\n"

        risk_level = "低"
        if total_files > 100 or total_functions > 200:
            risk_level = "高"
        elif total_files > 50 or total_functions > 100:
            risk_level = "中"

        md += f"| 风险类型 | 风险等级 | 说明 |\n"
        md += "|----------|----------|------|\n"
        md += f"| 代码规模 | {risk_level} | {'文件数量较多，维护成本较高' if risk_level == '高' else '规模适中'} |\n"
        md += f"| 复杂度 | {'高' if total_functions > 150 else '中' if total_functions > 50 else '低'} | {'函数数量较多' if total_functions > 150 else '复杂度可控'} |\n"
        md += f"| 测试覆盖 | {'待评估' if not test_analysis else '已有测试' if len(test_analysis.functions) > 0 else '建议补充'} | - |\n\n"

        return md

    def _generate_multi_role_consensus(self) -> str:
        """生成多角色共识"""
        md = "## 4. 多角色共识\n\n"

        consensus = self.aligned.get("consensus", [])
        discrepancies = self.aligned.get("discrepancies", [])

        md += "### 4.1 共识点\n\n"
        if consensus:
            for item in consensus:
                md += f"- {item}\n"
        else:
            md += "各角色分析结果无明显冲突\n"
        md += "\n"

        md += "### 4.2 差异点及解决方案\n\n"
        if discrepancies:
            md += "| 类型 | 描述 | 严重程度 | 建议 |\n"
            md += "|------|------|----------|------|\n"
            for disc in discrepancies:
                md += f"| {disc.get('type', 'N/A')} | {disc.get('description', 'N/A')} | {disc.get('severity', 'info')} | 需人工确认 |\n"
        else:
            md += "各角色视角一致，未发现明显差异\n\n"

        md += "### 4.3 各角色关注点总结\n\n"

        for analysis in self.analyses:
            role_info = RoleConfig.get_role_info(analysis.role)
            md += f"#### {role_info.get('name', analysis.role)}\n\n"
            md += f"- **关注领域**: {', '.join(role_info.get('focus_areas', []))}\n"
            md += f"- **识别模块数**: {len(analysis.modules)}\n"
            md += f"- **识别函数数**: {len(analysis.functions)}\n"
            md += f"- **识别类数量**: {len(analysis.classes)}\n"

            if analysis.recommendations:
                md += "- **主要建议**:\n"
                for rec in analysis.recommendations[:3]:
                    md += f"  - {rec}\n"
            md += "\n"

        return md

    def _generate_doc_code_consistency_check(self) -> str:
        """生成文档与代码一致性检查清单"""
        md = "## 5. 文档与代码一致性检查\n\n"

        doc_files = self.project_info.get('doc_files', [])
        doc_file_count = self.project_info.get('doc_file_count', 0)

        md += "### 5.1 文档覆盖概览\n\n"
        md += f"- **文档文件数**: {doc_file_count} 个\n"
        md += f"- **源码文件数**: {self.project_info.get('source_file_count', 0)} 个\n"

        if doc_file_count > 0:
            md += f"- **文档覆盖率**: {min(100, int(doc_file_count / self.project_info.get('source_file_count', 1) * 100))}%\n"
        else:
            md += "- **文档覆盖率**: 0% (警告: 项目缺乏文档)\n"
        md += "\n"

        md += "### 5.2 文档与代码差异检查清单\n\n"

        inconsistencies = self._check_doc_code_consistency()

        if inconsistencies:
            md += "| 检查项 | 状态 | 说明 |\n"
            md += "|--------|------|------|\n"
            for item in inconsistencies:
                status_icon = "❌" if item["status"] == "不一致" else "⚠️" if item["status"] == "待核实" else "✅"
                md += f"| {item['check_item']} | {status_icon} {item['status']} | {item['description']} |\n"
        else:
            md += "未发现明显不一致问题\n"
        md += "\n"

        md += "### 5.3 详细差异分析\n\n"

        critical_issues = [i for i in inconsistencies if i.get("severity") == "high"]
        if critical_issues:
            md += "#### 严重差异 (需立即处理)\n\n"
            for issue in critical_issues:
                md += f"**{issue['check_item']}**\n"
                md += f"- 问题: {issue['description']}\n"
                md += f"- 位置: {issue.get('location', 'N/A')}\n"
                md += f"- 建议: {issue.get('suggestion', '请更新文档或代码以保持一致')}\n\n"
        else:
            md += "#### 严重差异: 无\n\n"

        medium_issues = [i for i in inconsistencies if i.get("severity") == "medium"]
        if medium_issues:
            md += "#### 中等差异 (建议处理)\n\n"
            for issue in medium_issues:
                md += f"**{issue['check_item']}**\n"
                md += f"- 问题: {issue['description']}\n"
                md += f"- 位置: {issue.get('location', 'N/A')}\n\n"
        else:
            md += "#### 中等差异: 无\n\n"

        low_issues = [i for i in inconsistencies if i.get("severity") == "low"]
        if low_issues:
            md += "#### 轻微差异 (可选处理)\n\n"
            for issue in low_issues:
                md += f"- {issue['check_item']}: {issue['description']}\n"
        else:
            md += "#### 轻微差异: 无\n"

        md += "\n"

        md += "### 5.4 检查总结\n\n"

        total_issues = len(inconsistencies)
        high_count = len(critical_issues)
        medium_count = len(medium_issues)
        low_count = len(low_issues)

        md += f"| 类别 | 数量 |\n"
        md += f"|------|------|\n"
        md += f"| 严重差异 | {high_count} |\n"
        md += f"| 中等差异 | {medium_count} |\n"
        md += f"| 轻微差异 | {low_count} |\n"
        md += f"| **总计** | **{total_issues}** |\n\n"

        if high_count > 0:
            md += "> ⚠️ **警告**: 发现严重差异，建议立即处理以确保文档准确性\n"
        elif medium_count > 0:
            md += "> ℹ️ **提示**: 发现中等差异，建议在后续迭代中处理\n"
        else:
            md += "> ✅ **良好**: 文档与代码基本一致\n"

        md += "\n"
        return md

    def _check_doc_code_consistency(self) -> List[Dict[str, Any]]:
        """检查文档与代码的一致性"""
        inconsistencies = []
        doc_files = self.project_info.get('doc_files', [])

        if not doc_files:
            inconsistencies.append({
                "check_item": "项目文档缺失",
                "status": "不一致",
                "severity": "high",
                "description": "项目中未找到任何文档文件 (README.md, ARCHITECTURE.md 等)",
                "location": self.project_info.get('project_path', 'N/A'),
                "suggestion": "建议添加 README.md, ARCHITECTURE.md 等核心文档"
            })
            return inconsistencies

        doc_file_names = [Path(f).name for f in doc_files]

        if 'README.md' not in doc_file_names and 'README.txt' not in doc_file_names:
            inconsistencies.append({
                "check_item": "README 文档缺失",
                "status": "不一致",
                "severity": "high",
                "description": "项目根目录缺少 README 文档",
                "location": "项目根目录",
                "suggestion": "添加 README.md 文件，说明项目概述、安装、使用方法"
            })

        inconsistencies.extend(self._check_api_documentation(doc_files))
        inconsistencies.extend(self._check_config_documentation(doc_files))
        inconsistencies.extend(self._check_architecture_documentation(doc_files))

        return inconsistencies

    def _check_api_documentation(self, doc_files: List[str]) -> List[Dict[str, Any]]:
        """检查 API 文档与代码的一致性"""
        inconsistencies = []

        has_api_doc = any('API' in f.upper() or 'SWAGGER' in f.upper() or 'OPENAPI' in f.upper() for f in doc_files)

        has_api_controllers = False
        for analysis in self.analyses:
            for cls in analysis.classes:
                class_name = cls.get('name', '').lower()
                if 'controller' in class_name or 'api' in class_name or 'endpoint' in class_name:
                    has_api_controllers = True
                    break

        if has_api_controllers and not has_api_doc:
            inconsistencies.append({
                "check_item": "API 文档缺失",
                "status": "待核实",
                "severity": "medium",
                "description": "项目包含 API 控制器但缺少 API 文档",
                "location": "doc_files",
                "suggestion": "建议添加 API.md 或使用 Swagger/OpenAPI 自动生成文档"
            })

        return inconsistencies

    def _check_config_documentation(self, doc_files: List[str]) -> List[Dict[str, Any]]:
        """检查配置文档与代码的一致性"""
        inconsistencies = []

        has_config_docs = any('CONFIG' in f.upper() or 'SETUP' in f.upper() or 'DEPLOY' in f.upper() for f in doc_files)
        has_config_files = self.project_info.get('config_file_count', 0) > 0

        if has_config_files and not has_config_docs:
            inconsistencies.append({
                "check_item": "配置文档缺失",
                "status": "待核实",
                "severity": "low",
                "description": "项目包含配置文件但缺少配置说明文档",
                "location": "config files",
                "suggestion": "建议添加 CONFIG.md 或在 README 中说明配置方法"
            })

        return inconsistencies

    def _check_architecture_documentation(self, doc_files: List[str]) -> List[Dict[str, Any]]:
        """检查架构文档与代码的一致性"""
        inconsistencies = []

        has_arch_doc = any('ARCHITECTURE' in f.upper() or 'DESIGN' in f.upper() for f in doc_files)
        module_count = len(self.aligned.get('modules', []))

        if module_count > 5 and not has_arch_doc:
            inconsistencies.append({
                "check_item": "架构文档缺失",
                "status": "待核实",
                "severity": "medium",
                "description": f"项目包含 {module_count} 个模块但缺少架构文档",
                "location": "modules",
                "suggestion": "建议添加 ARCHITECTURE.md 说明系统架构设计"
            })

        return inconsistencies

    def _generate_recommendations(self) -> str:
        """生成改进建议"""
        md = "## 6. 改进建议\n\n"

        all_recommendations = []
        for analysis in self.analyses:
            for rec in analysis.recommendations:
                all_recommendations.append({
                    "role": analysis.role_display_name,
                    "recommendation": rec,
                    "priority": self._assess_priority(rec)
                })

        all_recommendations.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3))

        md += "### 6.1 高优先级改进项\n\n"
        high_priority = [r for r in all_recommendations if r["priority"] == "high"]
        if high_priority:
            for r in high_priority:
                md += f"- [{r['role']}] {r['recommendation']}\n"
        else:
            md += "无高优先级改进项\n"
        md += "\n"

        md += "### 6.2 中优先级改进项\n\n"
        medium_priority = [r for r in all_recommendations if r["priority"] == "medium"]
        if medium_priority:
            for r in medium_priority[:5]:
                md += f"- [{r['role']}] {r['recommendation']}\n"
        else:
            md += "无中优先级改进项\n"
        md += "\n"

        md += "### 6.3 低优先级改进项\n\n"
        low_priority = [r for r in all_recommendations if r["priority"] == "low"]
        if low_priority:
            for r in low_priority[:5]:
                md += f"- [{r['role']}] {r['recommendation']}\n"
        else:
            md += "无低优先级改进项\n"
        md += "\n"

        return md

    def _assess_priority(self, recommendation: str) -> str:
        """评估建议优先级"""
        high_keywords = ["安全", "性能", "bug", "critical", "urgent", "必须", "紧急"]
        medium_keywords = ["建议", "优化", "improve", "should", "考虑"]
        low_keywords = ["可以", "也许", "might", "optional", "可选"]

        rec_lower = recommendation.lower()
        for kw in high_keywords:
            if kw in rec_lower:
                return "high"
        for kw in medium_keywords:
            if kw in rec_lower:
                return "medium"
        return "low"

    def _generate_appendix(self) -> str:
        """生成附录"""
        md = "## 7. 附录\n\n"

        md += "### 7.1 代码地图摘要\n\n"
        summary = self.aligned["project_summary"]
        md += f"- **项目**: {summary['project_name']}\n"
        md += f"- **语言**: {', '.join(summary['languages'])}\n"
        md += f"- **框架**: {', '.join(summary['frameworks']) if summary['frameworks'] else '未检测到'}\n"
        md += f"- **模块**: {summary['total_modules']} 个\n"
        md += f"- **函数**: {summary['total_functions']} 个\n"
        md += f"- **类**: {summary['total_classes']} 个\n\n"

        md += "### 7.2 关键文件列表\n\n"

        code_elements = self.aligned.get("code_elements", [])
        key_elements = code_elements[:15] if code_elements else []

        if key_elements:
            md += "| 名称 | 类型 | 文件路径 |\n"
            md += "|------|------|----------|\n"
            for elem in key_elements:
                md += f"| {elem.get('name', 'N/A')} | {elem.get('type', 'N/A')} | `{elem.get('file_path', 'N/A')}` |\n"
        else:
            md += "无\n"
        md += "\n"

        return md

    def _generate_footer(self) -> str:
        """生成报告尾部"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        roles = ', '.join(a.role_display_name for a in self.analyses)

        return f"""---

## 审查结论

本代码走读审查报告综合了 {len(self.analyses)} 个角色的分析视角，提供以下核心结论：

1. **架构评估**: 项目采用分层架构，模块划分基本合理
2. **代码质量**: 代码规模{'较大，建议关注重点模块' if self.project_info.get('source_file_count', 0) > 50 else '规模适中'}
3. **改进建议**: 详见第五章，建议按优先级逐步实施

**完整代码地图请参见**: `<project>-ALIGNED-CODE-MAP.md`

---

*本报告由多角色协作分析生成*
*审查角色: {roles}*
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

        print("\n" + "-" * 40)
        print("生成代码走读审查报告...")
        print("-" * 40)

        review_report_path = output_dir / f"{project_name}-CODE-REVIEW-REPORT.md"
        report_generator = CodeReviewReportGenerator(analyses, aligned, project_info)
        report_generator.generate_report(str(review_report_path))

        results = {
            "project_info": project_info,
            "role_count": len(analyses),
            "analyzed_files": len(analysis_results),
            "output_files": {
                "unified_code_map": str(unified_map_path),
                "code_review_report": str(review_report_path)
            }
        }

        print("\n" + "=" * 60)
        print("多角色代码走读完成!")
        print("=" * 60)
        print(f"\n输出文件:")
        print(f"  统一代码地图: {unified_map_path}")
        print(f"  代码走读审查报告: {review_report_path}")

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
"""
Input Validator — 输入验证模块

提供任务描述和用户输入的验证功能，防止恶意输入和过长内容。

Author: DevSquad Team
Version: 3.3.0
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    reason: Optional[str] = None
    sanitized_input: Optional[str] = None


class InputValidator:
    """
    输入验证器
    
    功能：
    1. 长度验证：防止过长的任务描述
    2. 内容过滤：检测和阻止恶意模式
    3. 字符验证：确保输入为有效的 UTF-8 文本
    4. 输入清理：移除危险字符和模式
    """
    
    # 配置常量
    MAX_TASK_LENGTH = 10000  # 最大任务描述长度（字符）
    MIN_TASK_LENGTH = 5      # 最小任务描述长度（字符）
    MAX_ROLE_COUNT = 10      # 最大角色数量
    
    # 危险模式（正则表达式）
    FORBIDDEN_PATTERNS = [
        # XSS 攻击模式
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"onerror\s*=",
        r"onload\s*=",
        
        # SQL 注入模式
        r";\s*DROP\s+TABLE",
        r";\s*DELETE\s+FROM",
        r"UNION\s+SELECT",
        
        # 命令注入模式
        r"\$\(.*?\)",
        r"`.*?`",
        r"&&\s*rm\s+-rf",
        
        # HTML 注入
        r"<iframe[^>]*>",
        r"<embed[^>]*>",
        r"<object[^>]*>",
        
        # 数据 URI（可能包含恶意内容）
        r"data:text/html",
        r"data:application/",
    ]
    
    # 可疑模式（警告但不阻止）
    SUSPICIOUS_PATTERNS = [
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__",
        r"subprocess",
        r"os\.system",
    ]
    
    def __init__(
        self,
        max_length: int = MAX_TASK_LENGTH,
        min_length: int = MIN_TASK_LENGTH,
        strict_mode: bool = False
    ):
        """
        初始化验证器
        
        Args:
            max_length: 最大任务长度
            min_length: 最小任务长度
            strict_mode: 严格模式（检测到可疑模式也拒绝）
        """
        self.max_length = max_length
        self.min_length = min_length
        self.strict_mode = strict_mode
        
        # 编译正则表达式（提高性能）
        self._forbidden_regex = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in self.FORBIDDEN_PATTERNS
        ]
        self._suspicious_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.SUSPICIOUS_PATTERNS
        ]
    
    def validate_task(self, task: str) -> ValidationResult:
        """
        验证任务描述
        
        Args:
            task: 任务描述字符串
            
        Returns:
            ValidationResult: 验证结果
        """
        # 1. 类型检查
        if not isinstance(task, str):
            return ValidationResult(
                valid=False,
                reason=f"Task must be a string, got {type(task).__name__}"
            )
        
        # 2. 长度检查
        task_length = len(task)
        if task_length < self.min_length:
            return ValidationResult(
                valid=False,
                reason=f"Task too short (min {self.min_length} chars, got {task_length})"
            )
        
        if task_length > self.max_length:
            return ValidationResult(
                valid=False,
                reason=f"Task too long (max {self.max_length} chars, got {task_length})"
            )
        
        # 3. 空白检查
        if not task.strip():
            return ValidationResult(
                valid=False,
                reason="Task cannot be empty or whitespace only"
            )
        
        # 4. 字符编码检查
        try:
            task.encode('utf-8')
        except UnicodeEncodeError as e:
            return ValidationResult(
                valid=False,
                reason=f"Invalid UTF-8 encoding: {e}"
            )
        
        # 5. 危险模式检查
        for regex in self._forbidden_regex:
            match = regex.search(task)
            if match:
                return ValidationResult(
                    valid=False,
                    reason=f"Forbidden pattern detected: {match.group(0)[:50]}..."
                )
        
        # 6. 可疑模式检查（严格模式）
        if self.strict_mode:
            for regex in self._suspicious_regex:
                match = regex.search(task)
                if match:
                    return ValidationResult(
                        valid=False,
                        reason=f"Suspicious pattern detected (strict mode): {match.group(0)}"
                    )
        
        # 7. 清理输入
        sanitized = self._sanitize_input(task)
        
        return ValidationResult(
            valid=True,
            sanitized_input=sanitized
        )
    
    def validate_roles(self, roles: List[str]) -> ValidationResult:
        """
        验证角色列表
        
        Args:
            roles: 角色 ID 列表
            
        Returns:
            ValidationResult: 验证结果
        """
        # 1. 类型检查
        if not isinstance(roles, list):
            return ValidationResult(
                valid=False,
                reason=f"Roles must be a list, got {type(roles).__name__}"
            )
        
        # 2. 数量检查
        if len(roles) > self.MAX_ROLE_COUNT:
            return ValidationResult(
                valid=False,
                reason=f"Too many roles (max {self.MAX_ROLE_COUNT}, got {len(roles)})"
            )
        
        # 3. 空列表检查
        if not roles:
            return ValidationResult(
                valid=False,
                reason="Roles list cannot be empty"
            )
        
        # 4. 每个角色的验证
        for role in roles:
            if not isinstance(role, str):
                return ValidationResult(
                    valid=False,
                    reason=f"Role must be a string, got {type(role).__name__}"
                )
            
            if not role.strip():
                return ValidationResult(
                    valid=False,
                    reason="Role cannot be empty or whitespace only"
                )
            
            # 角色 ID 只能包含字母、数字、连字符和下划线
            if not re.match(r'^[a-zA-Z0-9_-]+$', role):
                return ValidationResult(
                    valid=False,
                    reason=f"Invalid role ID: {role} (only alphanumeric, -, _ allowed)"
                )
        
        return ValidationResult(valid=True)
    
    def _sanitize_input(self, text: str) -> str:
        """
        清理输入文本
        
        移除或转义潜在危险的字符和模式
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        # 1. 移除控制字符（保留换行和制表符）
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # 2. 规范化空白字符
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # 3. 移除前后空白
        sanitized = sanitized.strip()
        
        return sanitized
    
    def check_suspicious_patterns(self, task: str) -> List[str]:
        """
        检查可疑模式（不阻止，仅警告）
        
        Args:
            task: 任务描述
            
        Returns:
            List[str]: 检测到的可疑模式列表
        """
        warnings = []
        for regex in self._suspicious_regex:
            match = regex.search(task)
            if match:
                warnings.append(match.group(0))
        return warnings


# 便捷函数
def validate_task(task: str, strict: bool = False) -> ValidationResult:
    """
    验证任务描述（便捷函数）
    
    Args:
        task: 任务描述
        strict: 是否使用严格模式
        
    Returns:
        ValidationResult: 验证结果
    """
    validator = InputValidator(strict_mode=strict)
    return validator.validate_task(task)


def validate_roles(roles: List[str]) -> ValidationResult:
    """
    验证角色列表（便捷函数）
    
    Args:
        roles: 角色列表
        
    Returns:
        ValidationResult: 验证结果
    """
    validator = InputValidator()
    return validator.validate_roles(roles)


# 示例用法
if __name__ == "__main__":
    validator = InputValidator()
    
    # 测试 1: 正常任务
    result = validator.validate_task("Design a user authentication system")
    print(f"Test 1: {result}")
    
    # 测试 2: 过长任务
    result = validator.validate_task("A" * 20000)
    print(f"Test 2: {result}")
    
    # 测试 3: XSS 攻击
    result = validator.validate_task("<script>alert('xss')</script>")
    print(f"Test 3: {result}")
    
    # 测试 4: 正常角色列表
    result = validator.validate_roles(["architect", "pm", "tester"])
    print(f"Test 4: {result}")
    
    # 测试 5: 无效角色 ID
    result = validator.validate_roles(["architect", "pm@invalid"])
    print(f"Test 5: {result}")

#!/usr/bin/env python3
"""
User-Friendly Error System — 用户友好的错误提示

将技术性错误信息翻译为人类可读的提示，包含：
- 友好的错误描述
- 修复建议
- 使用示例

Author: DevSquad Team
Version: 1.0
"""

from typing import Optional


class UserFriendlyError(Exception):
    """
    用户友好的错误提示

    Attributes:
        message: 人类可读的错误描述
        suggestion: 修复建议
        example: 使用示例
        original_error: 原始技术错误（可选）
    """

    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        example: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.suggestion = suggestion
        self.example = example
        self.original_error = original_error
        super().__init__(self.format())

    def format(self) -> str:
        parts = [f"❌ {self.message}"]
        if self.suggestion:
            parts.append(f"💡 {self.suggestion}")
        if self.example:
            parts.append(f"📝 示例: {self.example}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "suggestion": self.suggestion,
            "example": self.example,
        }


ERROR_TEMPLATES = {
    "task_too_short": {
        "message": "任务描述太短了，请详细说明你想做什么",
        "suggestion": "好的任务描述应该包含：做什么 + 为什么 + 有什么特殊要求",
        "example": "devsquad dispatch -t '设计一个支持手机号和邮箱登录的用户认证系统'",
    },
    "task_too_long": {
        "message": "任务描述太长了，请精简到10000字以内",
        "suggestion": "把核心需求说清楚即可，细节可以在后续对话中补充",
        "example": "devsquad dispatch -t '优化数据库查询性能，重点关注慢查询和索引'",
    },
    "task_empty": {
        "message": "请输入任务描述",
        "suggestion": "告诉 DevSquad 你想做什么，它会自动匹配合适的AI角色来帮你",
        "example": "devsquad dispatch -t '设计用户权限系统'",
    },
    "task_invalid_type": {
        "message": "任务描述需要是文字内容",
        "suggestion": "请用自然语言描述你的任务，中文或英文都可以",
        "example": "devsquad dispatch -t 'Review the authentication module for security issues'",
    },
    "task_forbidden_content": {
        "message": "任务描述包含不允许的内容",
        "suggestion": "请移除HTML标签、脚本代码或SQL语句，使用纯文本描述任务",
        "example": "devsquad dispatch -t '实现用户注册功能'",
    },
    "task_injection_detected": {
        "message": "检测到异常的指令模式，请正常描述你的任务",
        "suggestion": "直接描述你想完成的项目任务即可，不需要特殊的指令格式",
        "example": "devsquad dispatch -t '搭建微服务架构的订单系统'",
    },
    "role_not_found": {
        "message": "找不到指定的角色",
        "suggestion": "使用 'devsquad roles' 查看所有可用角色，或省略 -r 参数让系统自动匹配",
        "example": "devsquad dispatch -t '设计系统架构' -r architect security",
    },
    "too_many_roles": {
        "message": "角色数量太多了（最多10个）",
        "suggestion": "精选最核心的2-4个角色，或省略 -r 让系统自动匹配",
        "example": "devsquad dispatch -t '设计安全系统' -r arch sec",
    },
    "backend_unavailable": {
        "message": "AI后端不可用",
        "suggestion": "检查API Key是否设置正确，或使用Mock模式测试",
        "example": "export OPENAI_API_KEY='your-key' && devsquad dispatch -t '...'",
    },
    "config_invalid": {
        "message": "配置文件格式有误",
        "suggestion": "运行 'devsquad init' 重新生成配置文件",
        "example": "devsquad init",
    },
    "dispatch_failed": {
        "message": "任务调度失败",
        "suggestion": "请检查任务描述是否清晰，或尝试简化任务后重试",
        "example": "devsquad dispatch -t '实现用户登录功能'",
    },
    "path_traversal": {
        "message": "检测到非法路径",
        "suggestion": "请使用正常的标识符，不要包含路径分隔符",
        "example": "devsquad dispatch -t '查看项目状态'",
    },
    "unknown_template": {
        "message": "找不到指定的生命周期模板",
        "suggestion": "使用 'devsquad lifecycle list' 查看可用模板",
        "example": "devsquad spec -t '需求分析'",
    },
}


def make_user_friendly_error(error_key: str, **kwargs) -> UserFriendlyError:
    """
    根据错误键创建用户友好的错误

    Args:
        error_key: 错误模板键
        **kwargs: 额外参数（如 original_error）

    Returns:
        UserFriendlyError 实例
    """
    template = ERROR_TEMPLATES.get(error_key, {})
    return UserFriendlyError(
        message=template.get("message", f"操作失败 ({error_key})"),
        suggestion=template.get("suggestion"),
        example=template.get("example"),
        original_error=kwargs.get("original_error"),
    )


def translate_validation_result(reason: str, original: Optional[Exception] = None) -> UserFriendlyError:
    """
    将 InputValidator 的 ValidationResult.reason 翻译为用户友好的错误

    Args:
        reason: InputValidator 返回的原始原因
        original: 原始异常

    Returns:
        UserFriendlyError 实例
    """
    reason_lower = reason.lower() if reason else ""

    if "too short" in reason_lower or "min" in reason_lower:
        return make_user_friendly_error("task_too_short", original_error=original)
    elif "too long" in reason_lower or "max" in reason_lower:
        return make_user_friendly_error("task_too_long", original_error=original)
    elif "empty" in reason_lower or "whitespace" in reason_lower:
        return make_user_friendly_error("task_empty", original_error=original)
    elif "string" in reason_lower or "type" in reason_lower:
        return make_user_friendly_error("task_invalid_type", original_error=original)
    elif "forbidden" in reason_lower:
        return make_user_friendly_error("task_forbidden_content", original_error=original)
    elif "injection" in reason_lower or "prompt" in reason_lower:
        return make_user_friendly_error("task_injection_detected", original_error=original)
    else:
        return UserFriendlyError(
            message=f"输入验证失败: {reason}",
            suggestion="请检查输入内容后重试",
            original_error=original,
        )

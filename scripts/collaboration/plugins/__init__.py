"""V4.0.0 P3-2: 插件热加载。

借鉴 TraeMultiAgentSkill 的 plugin_loader + hot_reload_watcher 理念。

三种加载路径：
1. BUILTIN_PLUGINS: 静态注册（启动时）
2. Hot Register API: hot_register() / hot_unregister()
3. Drop-in 目录扫描: plugins_extra/*.py + mtime 轮询

安全审查：
- 路径穿越三层防护：白名单目录 + 规范化路径 + 后缀检查
- reload 失败回滚到旧实例
- --no-hot-reload 完全关闭动态能力
- 审计日志记录每次 hot_register/hot_unregister
"""

from .hot_loader import PluginEntry, PluginHotLoader, PluginStatus

__all__ = [
    "PluginEntry",
    "PluginHotLoader",
    "PluginStatus",
]

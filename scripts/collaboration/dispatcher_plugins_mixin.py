"""Runtime plugin management mixin for :class:`MultiAgentDispatcher`.

Extracted from ``dispatcher.py`` (V4.5.20 size-gate refactor) so the core
dispatcher module keeps only composition + the ``dispatch`` orchestration
method. This mixin groups the V4.0.0 P3-2 hot-loading surface: register /
unregister / read / scan / reload of plugin instances through the injected
``PluginHotLoader``.

All methods share one precondition — ``plugins_enabled`` must be True and a
``plugin_hot_loader`` must be wired at construction; otherwise they raise
``RuntimeError`` so callers fail loudly instead of silently no-op'ing.
"""

from __future__ import annotations

from typing import Any

from .dispatcher_base import DispatcherBase


class DispatcherPluginsMixin(DispatcherBase):
    """Provides runtime plugin registration/hot-reload helpers."""

    plugins_enabled: bool
    plugin_hot_loader: Any

    # V4.0.0 P3-2: 插件热加载
    def register_plugin(self, name: str, plugin: Any) -> bool:
        """运行时注册插件实例。

        Args:
            name: 插件唯一名。
            plugin: 插件实例。

        Returns:
            True 注册成功，False 注册失败（plugins_enabled=False 或 no_hot_reload=True）。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return bool(self.plugin_hot_loader.hot_register(name, plugin))

    def unregister_plugin(self, name: str) -> bool:
        """运行时注销插件。

        Args:
            name: 插件名。

        Returns:
            True 注销成功，False 插件不存在。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return bool(self.plugin_hot_loader.hot_unregister(name))

    def register_builtin_plugin(self, name: str, plugin: Any) -> bool:
        """静态注册内置插件（不受 no_hot_reload 限制）。

        Args:
            name: 插件名。
            plugin: 插件实例。

        Returns:
            True 注册成功，False 已存在同名插件。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return bool(self.plugin_hot_loader.register_builtin(name, plugin))

    def get_plugin(self, name: str) -> Any | None:
        """获取已注册的插件实例。

        Args:
            name: 插件名。

        Returns:
            插件实例，未找到则返回 None。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return self.plugin_hot_loader.get_plugin(name)

    def list_plugins(self) -> list[str]:
        """列出所有已注册插件名。

        Returns:
            插件名列表。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return list(self.plugin_hot_loader.list_plugins())

    def scan_plugins(self) -> list[Any]:
        """扫描 drop-in 目录，加载新插件。

        Returns:
            新加载的 PluginEntry 列表。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return list(self.plugin_hot_loader.scan_dropin_dir())

    def reload_plugins(self) -> list[str]:
        """检查 mtime 和 checksum，重新加载变更的插件（失败回滚保留旧实例）。

        Returns:
            重载的插件名列表。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return list(self.plugin_hot_loader.reload_if_changed())


__all__ = ["DispatcherPluginsMixin"]

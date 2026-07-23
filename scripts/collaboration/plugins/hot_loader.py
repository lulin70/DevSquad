"""插件热加载核心实现。

支持三种加载路径，并提供路径穿越三层防护、reload 回滚、审计日志。

Usage:
    loader = PluginHotLoader(dropin_dir="/path/to/plugins_extra")
    loader.hot_register("my_plugin", MyPlugin())
    plugin = loader.get_plugin("my_plugin")

    # mtime 轮询
    changed = loader.reload_if_changed()
    if changed:
        print(f"Reloaded: {changed}")
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PluginStatus(str, Enum):
    """插件状态。"""

    REGISTERED = "registered"  # 已注册（hot_register 或 builtin）
    LOADED = "loaded"  # 从 drop-in 目录加载
    DISABLED = "disabled"  # 已禁用
    ERROR = "error"  # 加载失败


@dataclass
class PluginEntry:
    """插件注册条目。"""

    name: str
    plugin: Any
    status: PluginStatus
    source: str  # "builtin" | "hot_register" | "dropin"
    file_path: str = ""  # drop-in 插件的源文件路径
    mtime: float = 0.0  # 源文件最后修改时间
    checksum: str = ""  # 源文件 SHA256（用于检测内容变化）
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str = ""

    def is_active(self) -> bool:
        """是否处于活跃状态（可被使用）。"""
        return self.status in (PluginStatus.REGISTERED, PluginStatus.LOADED)


class PluginHotLoader:
    """V4.0.0 插件热加载器。

    三种加载路径：
    1. BUILTIN_PLUGINS: 启动时通过 register_builtin() 静态注册
    2. Hot Register API: 运行时 hot_register() / hot_unregister()
    3. Drop-in 目录扫描: scan_dropin_dir() + reload_if_changed()

    安全特性：
    - 路径穿越三层防护：_validate_path_safety()
    - reload 失败回滚：保留旧实例直到新实例加载成功
    - no_hot_reload=True 完全关闭动态能力
    - 审计日志：所有注册/注销操作记录到 _audit_log
    """

    # 安全约束
    _ALLOWED_SUFFIX = ".py"
    _MAX_FILE_SIZE = 1024 * 1024  # 1MB，防止加载超大文件

    def __init__(
        self,
        dropin_dir: str | Path = "plugins_extra",
        poll_interval_sec: int = 30,
        no_hot_reload: bool = False,
        audit_logger: Any = None,
    ) -> None:
        """初始化插件热加载器。

        Args:
            dropin_dir: drop-in 插件目录路径。
            poll_interval_sec: mtime 轮询间隔（秒）。
            no_hot_reload: True 则完全关闭动态加载能力。
            audit_logger: 可选的外部审计日志器，需有 log_plugin_op(method, name, ...) 方法。
        """
        self._dropin_dir = Path(dropin_dir).resolve()
        self._poll_interval = poll_interval_sec
        self._no_hot_reload = no_hot_reload
        self._external_audit_logger = audit_logger

        self._plugins: dict[str, PluginEntry] = {}
        self._mtimes: dict[str, float] = {}
        self._checksums: dict[str, str] = {}
        self._audit_log: list[dict[str, Any]] = []
        self._lock = threading.RLock()  # 并发安全

    # ------------------------------------------------------------------
    # Hot Register API
    # ------------------------------------------------------------------

    def hot_register(self, name: str, plugin: Any) -> bool:
        """运行时注册插件。

        Args:
            name: 插件名（唯一标识）。
            plugin: 插件实例。

        Returns:
            True 注册成功，False 注册失败（如 no_hot_reload=True）。
        """
        if self._no_hot_reload:
            self._log_audit("hot_register", name, success=False, reason="no_hot_reload enabled")
            logger.warning("hot_register blocked: no_hot_reload enabled")
            return False

        with self._lock:
            existing = self._plugins.get(name)
            if existing is not None:
                self._log_audit(
                    "hot_register", name, success=False, reason="plugin already registered"
                )
                logger.warning("Plugin %s already registered", name)
                return False

            entry = PluginEntry(
                name=name,
                plugin=plugin,
                status=PluginStatus.REGISTERED,
                source="hot_register",
            )
            self._plugins[name] = entry
            self._log_audit("hot_register", name, success=True)
            logger.info("Hot registered plugin: %s", name)
            return True

    def hot_unregister(self, name: str) -> bool:
        """运行时注销插件。

        Args:
            name: 插件名。

        Returns:
            True 注销成功，False 插件不存在或 no_hot_reload=True。
        """
        if self._no_hot_reload:
            self._log_audit("hot_unregister", name, success=False, reason="no_hot_reload enabled")
            return False

        with self._lock:
            if name not in self._plugins:
                self._log_audit("hot_unregister", name, success=False, reason="plugin not found")
                return False

            del self._plugins[name]
            self._mtimes.pop(name, None)
            self._checksums.pop(name, None)
            self._log_audit("hot_unregister", name, success=True)
            logger.info("Hot unregistered plugin: %s", name)
            return True

    def register_builtin(self, name: str, plugin: Any) -> bool:
        """静态注册内置插件（启动时调用，不受 no_hot_reload 限制）。

        Args:
            name: 插件名。
            plugin: 插件实例。

        Returns:
            True 注册成功，False 已存在同名插件。
        """
        with self._lock:
            if name in self._plugins:
                self._log_audit("register_builtin", name, success=False, reason="already exists")
                return False

            entry = PluginEntry(
                name=name,
                plugin=plugin,
                status=PluginStatus.REGISTERED,
                source="builtin",
            )
            self._plugins[name] = entry
            self._log_audit("register_builtin", name, success=True)
            return True

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def get_plugin(self, name: str) -> Any | None:
        """获取已注册的插件实例。"""
        with self._lock:
            entry = self._plugins.get(name)
            return entry.plugin if entry and entry.is_active() else None

    def list_plugins(self) -> list[str]:
        """列出所有已注册插件名。"""
        with self._lock:
            return [name for name, entry in self._plugins.items() if entry.is_active()]

    def list_all_entries(self) -> list[PluginEntry]:
        """列出所有插件条目（含禁用/错误的）。"""
        with self._lock:
            return list(self._plugins.values())

    def get_entry(self, name: str) -> PluginEntry | None:
        """获取插件条目（含元信息）。"""
        with self._lock:
            return self._plugins.get(name)

    # ------------------------------------------------------------------
    # Drop-in 目录扫描
    # ------------------------------------------------------------------

    def scan_dropin_dir(self) -> list[PluginEntry]:
        """扫描 drop-in 目录，加载新插件。

        路径穿越三层防护：
        1. 白名单目录：文件必须在 self._dropin_dir 下
        2. 规范化路径：resolve() 后检查
        3. 后缀检查：必须是 .py

        Returns:
            新加载的 PluginEntry 列表。
        """
        if self._no_hot_reload:
            logger.debug("scan_dropin_dir skipped: no_hot_reload enabled")
            return []

        if not self._dropin_dir.exists():
            return []

        new_entries: list[PluginEntry] = []
        with self._lock:
            for filepath in self._dropin_dir.glob("*.py"):
                if filepath.name == "__init__.py":
                    continue

                if not self._validate_path_safety(filepath):
                    continue

                plugin_name = filepath.stem
                if plugin_name in self._plugins:
                    continue  # 已注册（builtin 或 hot_register），跳过

                entry = self._load_plugin_file(plugin_name, filepath)
                if entry is not None:
                    self._plugins[plugin_name] = entry
                    self._mtimes[plugin_name] = entry.mtime
                    self._checksums[plugin_name] = entry.checksum
                    new_entries.append(entry)

        if new_entries:
            self._log_audit(
                "scan_dropin_dir",
                ",".join(e.name for e in new_entries),
                success=True,
                count=len(new_entries),
            )
            logger.info("Loaded %d new plugins from drop-in dir", len(new_entries))

        return new_entries

    def reload_if_changed(self) -> list[str]:
        """检查 mtime 和 checksum 变化，重新加载变更的插件。

        reload 失败回滚：保留旧实例直到新实例加载成功。

        Returns:
            重载的插件名列表。
        """
        if self._no_hot_reload:
            return []

        if not self._dropin_dir.exists():
            return []

        reloaded: list[str] = []
        with self._lock:
            for filepath in self._dropin_dir.glob("*.py"):
                if filepath.name == "__init__.py":
                    continue

                if not self._validate_path_safety(filepath):
                    continue

                plugin_name = filepath.stem
                entry = self._plugins.get(plugin_name)
                if entry is None or entry.source != "dropin":
                    continue  # 不是 drop-in 插件，跳过

                try:
                    stat = filepath.stat()
                except OSError as e:
                    logger.warning("Cannot stat %s: %s", filepath, e)
                    continue

                # 检查 mtime 和 checksum
                current_checksum = self._compute_checksum(filepath)
                if (
                    stat.st_mtime == entry.mtime
                    and current_checksum == entry.checksum
                ):
                    continue  # 未变化

                # reload，失败则保留旧实例
                old_entry = entry
                new_entry = self._load_plugin_file(plugin_name, filepath)
                if new_entry is not None:
                    self._plugins[plugin_name] = new_entry
                    self._mtimes[plugin_name] = new_entry.mtime
                    self._checksums[plugin_name] = new_entry.checksum
                    reloaded.append(plugin_name)
                    self._log_audit(
                        "reload", plugin_name, success=True,
                        old_mtime=old_entry.mtime, new_mtime=new_entry.mtime,
                    )
                    logger.info("Reloaded plugin: %s", plugin_name)
                else:
                    # 回滚：保留旧实例
                    self._log_audit(
                        "reload", plugin_name, success=False,
                        reason="load failed, kept old instance",
                    )
                    logger.warning(
                        "Reload %s failed, kept old instance (rollback)", plugin_name
                    )

        return reloaded

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _validate_path_safety(self, filepath: Path) -> bool:
        """路径穿越三层防护。

        1. 白名单目录：resolve() 后必须在 self._dropin_dir 下
        2. 后缀检查：必须是 .py
        3. 大小检查：不超过 _MAX_FILE_SIZE
        """
        try:
            resolved = filepath.resolve()
        except (OSError, RuntimeError) as e:
            logger.warning("Path resolve failed for %s: %s", filepath, e)
            return False

        # 防护 1：必须在 dropin_dir 下（防路径穿越）
        try:
            resolved.relative_to(self._dropin_dir)
        except ValueError:
            self._log_audit(
                "validate_path", filepath.name, success=False,
                reason="path traversal blocked", path=str(resolved),
            )
            logger.warning("Path traversal blocked: %s not in %s", resolved, self._dropin_dir)
            return False

        # 防护 2：后缀检查
        if resolved.suffix != self._ALLOWED_SUFFIX:
            self._log_audit(
                "validate_path", filepath.name, success=False,
                reason=f"invalid suffix: {resolved.suffix}",
            )
            logger.warning("Invalid suffix: %s", resolved)
            return False

        # 防护 3：大小检查
        try:
            size = resolved.stat().st_size
        except OSError as e:
            logger.warning("Cannot stat %s: %s", resolved, e)
            return False

        if size > self._MAX_FILE_SIZE:
            self._log_audit(
                "validate_path", filepath.name, success=False,
                reason=f"file too large: {size} bytes",
            )
            logger.warning("File too large: %s (%d bytes)", resolved, size)
            return False

        return True

    def _load_plugin_file(self, name: str, filepath: Path) -> PluginEntry | None:
        """从文件加载插件（reload 失败返回 None，不替换旧实例）。

        约定：插件文件需暴露 `create_plugin()` 函数返回插件实例。
        """
        try:
            # 计算校验值
            checksum = self._compute_checksum(filepath)
            mtime = filepath.stat().st_mtime

            # 动态导入
            module_name = f"_devsquad_plugin_{name}_{checksum[:8]}"
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot create module spec for {filepath}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 约定：插件文件必须暴露 create_plugin() 函数
            if not hasattr(module, "create_plugin"):
                raise RuntimeError(
                    f"Plugin {name} missing create_plugin() function"
                )

            plugin_instance = module.create_plugin()
            if plugin_instance is None:
                raise RuntimeError(f"Plugin {name} create_plugin() returned None")

            return PluginEntry(
                name=name,
                plugin=plugin_instance,
                status=PluginStatus.LOADED,
                source="dropin",
                file_path=str(filepath),
                mtime=mtime,
                checksum=checksum,
            )

        except Exception as e:
            # V4.2.1 bugfix: previously only (ImportError, AttributeError, RuntimeError,
            # OSError, SyntaxError) were caught. But create_plugin() can raise any
            # exception type (ValueError, TypeError, ZeroDivisionError, etc.) which
            # would propagate and crash the dispatcher. Plugin loaders must never let
            # plugin failures crash the host — catch Exception (excludes SystemExit,
            # KeyboardInterrupt, GeneratorExit which inherit from BaseException).
            self._log_audit(
                "load_plugin", name, success=False,
                reason=str(e), path=str(filepath),
            )
            logger.error("Failed to load plugin %s from %s: %s", name, filepath, e)
            return None

    @staticmethod
    def _compute_checksum(filepath: Path) -> str:
        """计算文件 SHA256 校验值。"""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _log_audit(
        self,
        method: str,
        name: str,
        success: bool,
        **extra: Any,
    ) -> None:
        """记录审计日志（内部 + 外部）。"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "name": name,
            "success": success,
            **extra,
        }
        self._audit_log.append(entry)

        # 同步到外部审计日志器（如有）
        if self._external_audit_logger is not None:
            try:
                self._external_audit_logger.log_plugin_op(
                    method=method, name=name, success=success, **extra
                )
            except (AttributeError, RuntimeError, OSError) as e:
                logger.warning("External audit log failed: %s", e)

    # ------------------------------------------------------------------
    # 审计日志查询
    # ------------------------------------------------------------------

    def get_audit_log(self) -> list[dict[str, Any]]:
        """获取审计日志副本。"""
        with self._lock:
            return list(self._audit_log)

    def clear_audit_log(self) -> None:
        """清空审计日志。"""
        with self._lock:
            self._audit_log.clear()

    # ------------------------------------------------------------------
    # 配置查询
    # ------------------------------------------------------------------

    @property
    def no_hot_reload(self) -> bool:
        return self._no_hot_reload

    @property
    def dropin_dir(self) -> Path:
        return self._dropin_dir

    @property
    def poll_interval_sec(self) -> int:
        return self._poll_interval


__all__ = [
    "PluginEntry",
    "PluginHotLoader",
    "PluginStatus",
]

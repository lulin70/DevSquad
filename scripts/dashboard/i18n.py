"""W3-T2: Internationalization (i18n) for the DevSquad dashboard.

Provides:
- TRANSLATIONS: dict mapping i18n keys to {zh: ..., en: ...} translations.
- I18nManager: class managing the active locale (reads/writes session_state).
- t(key, locale=None): translate a key to the active (or specified) locale.

Design:
- Pure dict lookup — no third-party i18n library.
- Only user-visible strings (page titles, buttons, statuses, settings) are
  translated; developer-facing logs/errors stay in English.
- Default locale is "zh" (Chinese), per DevSquad convention.
"""

from __future__ import annotations

from typing import Literal, cast

import streamlit as st

Locale = Literal["zh", "en"]

_DEFAULT_LOCALE: Locale = "zh"
_LOCALE_KEY = "_i18n_locale"
_SUPPORTED_LOCALES: tuple[Locale, ...] = ("zh", "en")


# ── Translation table ──
# Each key maps to {"zh": <Chinese>, "en": <English>}.
# Keep keys stable — they are the contract between code and translations.
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Page titles (sidebar navigation)
    "page.overview": {"zh": "概览", "en": "Overview"},
    "page.phases": {"zh": "阶段", "en": "Phases"},
    "page.mapping": {"zh": "命令映射", "en": "Mapping"},
    "page.gates": {"zh": "质量门", "en": "Gates"},
    "page.performance": {"zh": "性能", "en": "Performance"},
    "page.task_dispatch": {"zh": "任务调度", "en": "Task Dispatch"},
    "page.dag": {"zh": "依赖图", "en": "DAG"},
    # Buttons
    "btn.run_all": {"zh": "运行全部阶段", "en": "Run All Phases"},
    "btn.reset_state": {"zh": "重置状态", "en": "Reset State"},
    "btn.generate_report": {"zh": "生成报告", "en": "Generate Report"},
    "btn.refresh": {"zh": "刷新", "en": "Refresh"},
    "btn.refresh_data": {"zh": "刷新数据", "en": "Refresh Data"},
    "btn.export_status": {"zh": "导出状态", "en": "Export Status"},
    # Status labels
    "status.pending": {"zh": "待执行", "en": "Pending"},
    "status.running": {"zh": "执行中", "en": "Running"},
    "status.completed": {"zh": "已完成", "en": "Completed"},
    "status.failed": {"zh": "失败", "en": "Failed"},
    "status.skipped": {"zh": "跳过", "en": "Skipped"},
    "status.blocked": {"zh": "阻塞", "en": "Blocked"},
    # Settings
    "setting.auto_refresh": {"zh": "自动刷新 (30秒)", "en": "Auto Refresh (30s)"},
    "setting.show_details": {"zh": "显示详情", "en": "Show Details"},
    "setting.dark_mode": {"zh": "深色模式", "en": "Dark Mode"},
    "setting.language": {"zh": "语言", "en": "Language"},
    # Sidebar sections
    "sidebar.navigation": {"zh": "导航", "en": "Navigation"},
    "sidebar.settings": {"zh": "设置", "en": "Settings"},
    "sidebar.quick_actions": {"zh": "快捷操作", "en": "Quick Actions"},
    "sidebar.admin": {"zh": "管理员", "en": "Admin"},
    # Misc
    "label.last_updated": {"zh": "最后更新", "en": "Last Updated"},
    "label.session": {"zh": "会话", "en": "Session"},
}


class I18nManager:
    """Manage active locale for the dashboard.

    The active locale is persisted in ``st.session_state["_i18n_locale"]``.
    On first access, defaults to :data:`_DEFAULT_LOCALE`.
    """

    @staticmethod
    def get_locale() -> Locale:
        """Return the active locale, defaulting to 'zh' if unset."""
        locale = st.session_state.get(_LOCALE_KEY, _DEFAULT_LOCALE)
        if locale not in _SUPPORTED_LOCALES:
            locale = _DEFAULT_LOCALE
        return cast(Locale, locale)

    @staticmethod
    def set_locale(locale: Locale) -> None:
        """Persist the active locale to session_state."""
        if locale not in _SUPPORTED_LOCALES:
            raise ValueError(
                f"Unsupported locale: {locale!r}. Supported: {_SUPPORTED_LOCALES}"
            )
        st.session_state[_LOCALE_KEY] = locale

    @staticmethod
    def render_language_toggle() -> Locale:
        """Render a language selector in the sidebar.

        Returns:
            The active locale after the user's selection (or default).
        """
        current = I18nManager.get_locale()
        options = list(_SUPPORTED_LOCALES)
        labels = {"zh": "中文", "en": "English"}
        # Use a selectbox with friendly labels
        label_options = [labels[loc] for loc in options]
        current_idx = options.index(current)
        selected_idx = st.selectbox(
            t("setting.language"),
            options=range(len(label_options)),
            format_func=lambda i: label_options[i],
            index=current_idx,
            key="_i18n_locale_select",
        )
        new_locale = options[selected_idx]
        if new_locale != current:
            I18nManager.set_locale(new_locale)
        return new_locale


def t(key: str, locale: Locale | None = None) -> str:
    """Translate a key to the active (or specified) locale.

    Args:
        key: Translation key (e.g. ``"page.overview"``).
        locale: Optional locale override. If None, uses the active session locale.

    Returns:
        The translated string. If the key is unknown, returns the key itself
        (so developers can spot missing translations easily).
    """
    if locale is None:
        # Use a safe default when called outside a Streamlit context
        try:
            locale = I18nManager.get_locale()
        except Exception:  # noqa: BLE001 — broad on purpose for non-streamlit contexts
            locale = _DEFAULT_LOCALE

    if key not in TRANSLATIONS:
        return key

    entry = TRANSLATIONS[key]
    if locale in entry:
        return entry[locale]
    # Fallback to default locale if the requested locale is missing
    return entry.get(_DEFAULT_LOCALE, key)


def get_supported_locales() -> tuple[Locale, ...]:
    """Return the tuple of supported locales."""
    return _SUPPORTED_LOCALES


def get_default_locale() -> Locale:
    """Return the default locale used when no preference is set."""
    return _DEFAULT_LOCALE

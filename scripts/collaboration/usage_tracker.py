#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UsageTracker - 轻量级功能使用追踪系统

用于追踪 DevSquad 各组件的使用情况，为优化决策提供数据支持。
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict


class UsageTracker:
    """轻量级功能使用追踪器
    
    特性：
    - 线程安全的使用统计
    - 自动持久化到文件
    - 支持错误追踪
    - 生成使用报告
    """
    
    def __init__(self, persist_file: Optional[str] = None):
        """初始化追踪器
        
        Args:
            persist_file: 持久化文件路径，默认为 .usage_stats.json
        """
        self.stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "first_used": None,
            "last_used": None,
            "errors": 0,
        })
        self.persist_file = persist_file or ".usage_stats.json"
        self._lock = threading.RLock()
        self._load_stats()
    
    def track(self, feature_name: str, success: bool = True, 
              metadata: Optional[Dict] = None) -> None:
        """追踪功能使用
        
        Args:
            feature_name: 功能名称，格式如 "dispatcher.dispatch"
            success: 是否成功执行
            metadata: 额外的元数据（可选）
        """
        with self._lock:
            stat = self.stats[feature_name]
            stat["count"] += 1
            
            now = datetime.now().isoformat()
            if stat["first_used"] is None:
                stat["first_used"] = now
            stat["last_used"] = now
            
            if not success:
                stat["errors"] += 1
            
            if metadata:
                if "metadata" not in stat:
                    stat["metadata"] = []
                stat["metadata"].append(metadata)
                # 只保留最近 10 条元数据
                stat["metadata"] = stat["metadata"][-10:]
    
    def get_stats(self, feature_name: Optional[str] = None) -> Dict:
        """获取统计数据
        
        Args:
            feature_name: 功能名称，None 表示获取所有统计
            
        Returns:
            统计数据字典
        """
        with self._lock:
            if feature_name:
                return dict(self.stats.get(feature_name, {}))
            return {k: dict(v) for k, v in self.stats.items()}
    
    def get_top_features(self, limit: int = 10) -> List[Tuple[str, int]]:
        """获取使用最多的功能
        
        Args:
            limit: 返回的功能数量
            
        Returns:
            [(功能名, 调用次数), ...] 列表
        """
        with self._lock:
            sorted_features = sorted(
                self.stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )
            return [(name, stats["count"]) for name, stats in sorted_features[:limit]]
    
    def get_unused_features(self, all_features: List[str]) -> List[str]:
        """获取从未使用的功能
        
        Args:
            all_features: 所有功能名称列表
            
        Returns:
            未使用的功能名称列表
        """
        with self._lock:
            used = set(self.stats.keys())
            return [f for f in all_features if f not in used]
    
    def get_error_prone_features(self, min_calls: int = 5, 
                                  error_threshold: float = 0.1) -> List[Tuple[str, float]]:
        """获取高错误率的功能
        
        Args:
            min_calls: 最小调用次数阈值
            error_threshold: 错误率阈值（0.1 = 10%）
            
        Returns:
            [(功能名] 列表
        """
        with self._lock:
            error_prone = []
            for name, stat in self.stats.items():
                if stat["count"] >= min_calls:
                    error_rate = stat["errors"] / stat["count"]
                    if error_rate >= error_threshold:
                        error_prone.append((name, error_rate))
            return sorted(error_prone, key=lambda x: x[1], reverse=True)
    
    def generate_report(self) -> str:
        """生成使用报告
        
        Returns:
            Markdown 格式的报告文本
        """
        with self._lock:
            total_calls = sum(s["count"] for s in self.stats.values())
            total_errors = sum(s["errors"] for s in self.stats.values())
            
            lines = [
                "# DevSquad 功能使用报告",
                f"\n**生成时间**: {datetime.now().isoformat()}",
                f"**追踪功能数**: {len(self.stats)}",
                f"**总调用次数**: {total_calls:,}",
                f"**总错误次数**: {total_errors}",
                f"**总体错误率**: {(total_errors/max(1,total_calls)*100):.2f}%",
                "\n## Top 10 最常用功能\n",
            ]
            
            for name, count in self.get_top_features(10):
                stat = self.stats[name]
                error_rate = (stat["errors"] / max(1, stat["count"])) * 100
                lines.append(f"- **{name}**: {count:,} 次调用, 错误率 {error_rate:.1f}%")
            
            # 按组件分类
            lines.append("\n## 按组件分类\n")
            by_component = defaultdict(int)
            for name, stat in self.stats.items():
                component = name.split(".")[0] if "." in name else "other"
                by_component[component] += stat["count"]
            
            for component, count in sorted(by_component.items(), 
                                          key=lambda x: x[1], reverse=True):
                pct = (count / max(1, total_calls)) * 100
                lines.append(f"- **{component}**: {count:,} 次调用 ({pct:.1f}%)")
            
            # 高错误率功能
            error_prone = self.get_error_prone_features()
            if error_prone:
                lines.append("\n## ⚠️ 高错误率功能\n")
                for name, error_rate in error_prone[:5]:
                    stat = self.stats[name]
                    lines.append(
                        f"- **{name}**: 错误率 {error_rate*100:.1f}% "
                        f"({stat['errors']}/{stat['count']} 次调用)"
                    )
            
            # 使用频率分布
            lines.append("\n## 使用频率分布\n")
            freq_buckets = {
                "高频 (>100次)": 0,
                "中频 (10-100次)": 0,
                "低频 (1-10次)": 0,
            }
            for stat in self.stats.values():
                count = stat["count"]
                if count > 100:
                    freq_buckets["高频 (>100次)"] += 1
                elif count >= 10:
                    freq_buckets["中频 (10-100次)"] += 1
                else:
                    freq_buckets["低频 (1-10次)"] += 1
            
            for bucket, num in freq_buckets.items():
                pct = (num / max(1, len(self.stats))) * 100
                lines.append(f"- {bucket}: {num} 个功能 ({pct:.1f}%)")
            
            return "\n".join(lines)
    
    def save(self) -> bool:
        """保存统计数据到文件
        
        Returns:
            是否保存成功
        """
        with self._lock:
            try:
                with open(self.persist_file, 'w', encoding='utf-8') as f:
                    json.dump(dict(self.stats), f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                print(f"Failed to save usage stats: {e}")
                return False
    
    def _load_stats(self) -> None:
        """从文件加载统计数据"""
        try:
            if Path(self.persist_file).exists():
                with open(self.persist_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.stats.update(loaded)
        except Exception as e:
            print(f"Failed to load usage stats: {e}")
    
    def clear(self) -> int:
        """清空所有统计数据
        
        Returns:
            清空的功能数量
        """
        with self._lock:
            count = len(self.stats)
            self.stats.clear()
            return count
    
    def export_json(self) -> str:
        """导出为 JSON 字符串
        
        Returns:
            JSON 格式的统计数据
        """
        with self._lock:
            return json.dumps(dict(self.stats), indent=2, ensure_ascii=False)


# 全局单例
_global_tracker: Optional[UsageTracker] = None
_tracker_lock = threading.Lock()


def get_tracker() -> UsageTracker:
    """获取全局追踪器实例（线程安全）
    
    Returns:
        全局 UsageTracker 实例
    """
    global _global_tracker
    if _global_tracker is None:
        with _tracker_lock:
            if _global_tracker is None:
                _global_tracker = UsageTracker()
    return _global_tracker


def track_usage(feature_name: str, success: bool = True, 
                metadata: Optional[Dict] = None) -> None:
    """便捷函数：追踪功能使用
    
    Args:
        feature_name: 功能名称
        success: 是否成功
        metadata: 元数据
    """
    get_tracker().track(feature_name, success, metadata)


def get_usage_stats(feature_name: Optional[str] = None) -> Dict:
    """便捷函数：获取统计数据
    
    Args:
        feature_name: 功能名称，None 表示获取所有
        
    Returns:
        统计数据字典
    """
    return get_tracker().get_stats(feature_name)


def generate_usage_report() -> str:
    """便捷函数：生成使用报告
    
    Returns:
        Markdown 格式的报告
    """
    return get_tracker().generate_report()


def save_usage_stats() -> bool:
    """便捷函数：保存统计数据
    
    Returns:
        是否保存成功
    """
    return get_tracker().save()


## 🔬 MCE 集成方案 — 多角色分析报告

> **时间**: 2026-04-17 13:03 | **耗时**: 0.00s
> **参与**: 架构师 / 独立开发者 / 测试专家

### 🎯 核心共识

| 维度 | 结论 |
|------|------|
| **接入方式** | **Facade 直接 import + Adapter 包装层** |
| **初始化策略** | 懒加载 (lazy init), import失败时 graceful degrade |
| **集成点** | Phase A (capture) 优先, Phase B/C 可选 |
| **MVP 范围** | mce_adapter.py(~150行) + memory_bridge 3处改动 |
| **测试策略** | Mock契约测试 + 零回归保证 |

### 🏗️ 推荐架构: MCEAdapter

```python
# mce_adapter.py — 新建文件，~150行
class MCEAdapter:
    '''MCE 记忆分类引擎适配器'''

    def __init__(self, enable: bool = False):
        self._available = False
        self._facade = None
        if enable:
            self._try_init()

    def _try_init(self):
        try:
            from memory_classification_engine import MemoryClassificationEngineFacade
            self._facade = MemoryClassificationEngineFacade()
            self._available = True
        except (ImportError, Exception) as e:
            self._available = False  # 优雅降级

    def classify(self, text: str, ctx: Dict = None) -> Optional[Dict]:
        '''分类文本，返回MCE类型或None(MCE不可用时)'''
        if not self._available or not self._facade:
            return None
        try:
            result = self._facade.classify_message(text, ctx)
            return result  # {'type': 'decision', 'confidence': 0.9, ...}
        except Exception as e:
            return None  # 任何异常都不影响主流程

    @property
    def is_available(self) -> bool:
        return self._available
```

### 📝 改动清单

| 文件 | 改动 | 行数 | 说明 |
|------|------|------|------|
| `mce_adapter.py` | **新建** | ~150 | MCEAdapter 类 + 异常处理 |
| `memory_bridge.py` | **修改** | ~25 | __init__ 加 adapter 参数; capture_execution 加分类; recall 加过滤 |
| `dispatcher.py` | **修改** | ~8 | dispatch() 内存步骤加 MCE 分支判断 |
| `__init__.py` | **修改** | ~5 | 导出 MCEAdapter 符号 |
| `mce_adapter_test.py` | **新建** | ~40 | 单元测试(MockMCE) |
| `mce_contract_test.py` | **新建** | ~15 | 契约测试(真实MCE实例) |
| **合计** | | **~243行** | |

### 💬 各角色核心观点

**架构师**:
  - 建议: 采用 Facade 直接 import + Adapter 包装层
  - MVP: 只做 Phase A (capture_execution 分类), ~120行
  - 风险: MCE 的 classify_message 可能较慢(含模型推理?) —— 需要异步化; MEMORY_TYPES 枚举值可能与我们的 MemoryType 不兼容 —— 需要映射表

**开发者**:
  - 建议: 实现最小可行集成 + Mock测试框架
  - MVP: mce_adapter.py + memory_bridge 3处改动 + mock测试

**测试专家**:
  - 建议: 分层测试 + 契约测试(contract test)
  - MVP: Layer1+Layer2 = 35 cases, 确保 Layer3 零回归

### ⚖️ 冲突记录

**冲突1**: MVP范围: 只做Phase A 还是 A+B一起做
- 方: architect, solo-coder
- 建议: 先做 Phase A (capture_only), MVP 控制在 150 行内, 后续迭代加 Phase B/C

**冲突2**: 是否需要MockMCE还是直接用真实实例测试
- 方: solo-coder, tester
- 建议: 先做 Phase A (capture_only), MVP 控制在 150 行内, 后续迭代加 Phase B/C

### ➡️ 下一步行动

1. [ ] 创建 `scripts/collaboration/mce_adapter.py` — MCEAdapter 实现
2. [ ] 修改 `memory_bridge.py` — 3处集成点 (capture/recall/shutdown)
3. [ ] 编写 `mce_adapter_test.py` — MockMCE 单元测试
4. [ ] 编写 `mce_contract_test.py` — 真实MCE契约测试 (标记optional)
5. [ ] 运行全量回归确保零退化
6. [ ] 更新 docs/planning/ 和 SKILL.md 反映 MCE 集成状态

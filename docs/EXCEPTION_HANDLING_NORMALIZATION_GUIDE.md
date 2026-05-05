# DevSquad 异常处理规范化指南

**版本**: V3.4.0
**日期**: 2026-05-04
**目标**: 将40处宽泛异常处理规范化为具体异常类型

---

## 📊 当前状态

### 异常处理分布

| 模块 | 数量 | 优先级 | 状态 |
|------|------|--------|------|
| **mce_adapter.py** | 12 | P0 | ⏳ 待规范化 |
| **dispatcher.py** | 10 | P0 | ⏳ 待规范化 |
| **lifecycle_protocol.py** | 8 | P1 | ⏳ 待规范化 |
| **llm_retry.py** | 3 | P1 | ⏳ 待规范化 |
| **workflow_engine.py** | 1 | P2 | ⏳ 待规范化 |
| **verification_gate.py** | 1 | P2 | ⏳ 待规范化 |
| **task_completion_checker.py** | 3 | P2 | ⏳ 待规范化 |
| **prompt_assembler.py** | 2 | P2 | ⏳ 待规范化 |
| **checkpoint_manager.py** | 1 | P2 | ⏳ 待规范化 |

**总计**: 40处

---

## 🎯 规范化原则

### 原则1: 使用具体异常类型

```python
# ❌ 错误: 宽泛异常
try:
    result = dangerous_operation()
except Exception as e:
    logger.error(f"Error: {e}")

# ✅ 正确: 具体异常
try:
    result = dangerous_operation()
except (ValueError, TypeError, KeyError) as e:
    logger.error(f"Operation failed with {type(e).__name__}: {e}")
except ImportError as e:
    logger.error(f"Missing dependency: {e}")
```

### 原则2: 分层捕获异常

```python
# ✅ 最佳实践: 从最具体到最宽泛
try:
    result = complex_operation()
except (ConnectionError, TimeoutError) as e:
    # 网络相关错误
    raise OperationError(f"Network error in {func_name}: {e}") from e
except (ValueError, KeyError) as e:
    # 数据格式错误
    raise DataError(f"Invalid data format: {e}") from e
except Exception as e:
    # 其他未预期错误（保留作为最后防线）
    logger.error(f"Unexpected error in {func_name}: {type(e).__name__}: {e}")
    raise
```

### 原则3: 异常链保留 (raise ... from e)

```python
# ❌ 错误: 丢失原始异常上下文
try:
    value = config[key]
except KeyError:
    raise ValueError(f"Missing key: {key}")

# ✅ 正确: 保留完整异常链
try:
    value = config[key]
except KeyError as e:
    raise ValueError(f"Missing configuration key: {key}") from e
```

### 原则4: 日志级别分级

```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: 开发调试信息
logger.debug(f"Processing item {item_id}")

# INFO: 重要业务事件
logger.info(f"Successfully processed {item_id}")

# WARNING: 可恢复的问题
logger.warning(f"Retry attempt {retry_count} for {item_id}")

# ERROR: 需要关注但可继续
logger.error(f"Failed to process {item_id}: {error}", exc_info=True)

# CRITICAL: 不可恢复的错误
logger.critical(f"System failure: {error}", exc_info=True)
```

---

## 📝 各模块规范化方案

### 1. mce_adapter.py (12处)

#### 当前问题
```python
# L164, L168, L210, L231, L252, L353, L380, L402, L417
except Exception as e:
    self._status.available = False
    self._status.init_error = f"{type(e).__name__}: {e}"
```

#### 规范化方案
```python
# 改为具体异常类型
except ImportError as e:
    self._status.available = False
    self._status.init_error = f"CarryMem not installed: {e}"
    self._adapter_type = "none"
except (AttributeError, ModuleNotFoundError) as e:
    self._status.available = False
    self._status.init_error = f"CarryMem module error: {e}"
    self._adapter_type = "none"
except Exception as e:
    # 保留作为最后防线，记录详细日志
    logging.getLogger(__name__).warning(
        f"Unexpected error initializing MCEAdapter: {type(e).__name__}: {e}"
    )
    self._status.available = False
    self._status.init_error = f"{type(e).__name__}: {e}"
    self._adapter_type = "none"
```

---

### 2. dispatcher.py (10处)

#### 当前问题
```python
# L385, L454, L490, L660, L677, L706, L723, L774, L779, L919, L945, L951
except Exception as e:
    # 各种不同的处理方式
```

#### 规范化方案
```python
# 根据操作类型分类
# 文件操作 → (IOError, OSError, PermissionError)
# 网络操作 → (ConnectionError, TimeoutError)
# 数据操作 → (ValueError, KeyError, TypeError)
# 导入操作 → (ImportError, ModuleNotFoundError)

# 示例: L385 - Worker 执行异常
except (ValueError, TypeError, AttributeError) as worker_err:
    errors.append(f"Worker execution error: {worker_err}")
    logging.getLogger(__name__).debug(
        f"Worker {role} failed with {type(worker_err).__name__}: {worker_err}"
    )
except Exception as e:
    # 未预期的严重错误
    errors.append(f"Critical worker error: {type(e).__name__}: {e}")
    logging.getLogger(__name__).error(
        f"Unexpected error in worker {role}: {type(e).__name__}: {e}",
        exc_info=True
    )
```

---

### 3. lifecycle_protocol.py (8处)

#### 规范化重点
- 阶段转换异常 → `ValueError`, `TypeError`
- 状态检查异常 → `AttributeError`, `KeyError`
- 超时异常 → `TimeoutError`
- I/O 异常 → `IOError`, `OSError`

---

## 🔧 实施步骤

### 第1批: mce_adapter.py + dispatcher.py (22处) [预计2h]

**优先级**: P0 - 核心模块，影响最大

**检查清单**:
- [ ] 所有 `except Exception` 替换为具体类型
- [ ] 添加 `logging.getLogger(__name__)` 日志
- [ ] 关键路径添加 `exc_info=True`
- [ ] 保留异常链 `from e`

### 第2批: lifecycle_protocol.py + llm_retry.py (11处) [预计1.5h]

**优先级**: P1 - 协议层和重试机制

**检查清单**:
- [ ] 重试逻辑中的异常分类
- [ ] 超时和取消异常特殊处理
- [ ] 状态机转换异常细化

### 第3批: 其他模块 (7处) [预计1h]

**优先级**: P2 - 辅助模块

**检查清单**:
- [ ] workflow_engine.py
- [ ] verification_gate.py
- [ ] task_completion_checker.py
- [ ] prompt_assembler.py
- [ ] checkpoint_manager.py

---

## ✅ 验证标准

### 自动化验证
```bash
# 运行测试确保无回归
pytest tests/ -v --tb=short

# 检查异常覆盖率
grep -r "except Exception" scripts/collaboration/ | wc -l
# 目标: < 10 (仅保留在真正需要的位置)
```

### 代码审查标准
- [x] 无裸 `except:` 语句
- [x] 无不必要的 `except Exception` (应使用具体类型)
- [x] 所有关键路径有日志记录
- [x] 异常信息包含足够的上下文
- [x] 异常链正确传递 (`from e`)

---

## 📈 预期收益

| 指标 | 改进前 | 改进后 | 提升 |
|------|--------|--------|------|
| **异常诊断效率** | 低（需查日志） | 高（直接看异常类型） | +80% |
| **错误定位速度** | 慢（通用错误） | 快（精确位置） | +70% |
| **代码可读性** | 中 | 高 | +50% |
| **生产稳定性** | 好 | 优秀 | +20% |

---

## 🎓 最佳实践示例

### 完整的异常处理模板

```python
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def safe_operation(param: str) -> Optional[Any]:
    """
    安全执行操作的模板函数
    
    Args:
        param: 操作参数
        
    Returns:
        操作结果或None
        
    Raises:
        ValueError: 参数无效
        ConnectionError: 连接失败
        OperationError: 操作失败
    """
    try:
        # 1. 参数验证
        if not param or not isinstance(param, str):
            raise ValueError(f"Invalid parameter: expected non-empty string, got {type(param)}")
        
        # 2. 执行核心逻辑
        result = core_logic(param)
        
        # 3. 返回结果
        return result
        
    except ValueError as ve:
        # 参数问题 - 直接抛出给调用者
        logger.warning(f"Parameter validation failed: {ve}")
        raise
        
    except (ConnectionError, TimeoutError) as ce:
        # 网络问题 - 包装后重抛
        logger.error(f"Network operation failed: {ce}", exc_info=True)
        raise OperationError(f"Cannot connect to service: {ce}") from ce
        
    except (KeyError, IndexError) as ke:
        # 数据访问问题 - 包装后重抛
        logger.error(f"Data access error: {ke}", exc_info=True)
        raise OperationError(f"Data structure mismatch: {ke}") from ke
        
    except Exception as e:
        # 未预期的严重错误 - 记录并包装
        logger.critical(
            f"UNEXPECTED ERROR in safe_operation: "
            f"type={type(e).__name__}, param={param!r}, error={e}",
            exc_info=True
        )
        raise OperationError(
            f"Unexpected error during operation: {type(e).__name__}: {e}"
        ) from e
```

---

## 📚 参考资料

- [Python Exception Hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy)
- [PEP 3151 - Exception Chaining](https://www.python.org/dev/peps/pep-3151/)
- [Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [Google Python Style Guide - Exceptions](https://google.github.io/styleguide/pyguide.html#91-exceptions)

---

**创建时间**: 2026-05-04  
**预计完成时间**: 2026-05-11  
**负责人**: DevSquad Coder Role  
**审核人**: DevSquad Architect Role

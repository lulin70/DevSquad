# Moka LLM 调优指南

## 问题背景

本地 Moka 服务在处理复杂推理任务(如 DevSquad 多角色协作)时可能遇到超时,表现为:
```
MokaAIBackend.generate failed after 3 attempts: Request timed out.
```

## V4.10.0 调优改进

### 1. 默认超时优化

**修改前(V4.5.2)**:
- 单次请求超时: 30秒
- 重试次数: 3次
- 总计最大等待: 30s × 3 = 90秒 + 重试间隔

**修改后(V4.10.0)**:
- 单次请求超时: **90秒** (3倍提升)
- 重试次数: **2次** (减少不必要的等待)
- 总计最大等待: 90s × 2 = **180秒** (约3分钟)

### 2. 环境变量动态调优

现在支持通过 `MOKA_TIMEOUT` 环境变量动态调整超时,无需修改代码:

```bash
# 测试阶段使用更长超时(5分钟)
export MOKA_TIMEOUT=300

# 生产环境使用默认配置(90秒)
unset MOKA_TIMEOUT

# 快速验证使用短超时(30秒)
export MOKA_TIMEOUT=30
```

### 3. 使用方法

#### 方法 A: 使用默认配置(推荐)

直接使用,无需额外配置:
```bash
cd /Users/lin/trae_projects/DevSquad
python3 scripts/cli.py dispatch "Design authentication system" \
    --backend moka --roles architect security
```

#### 方法 B: 环境变量覆盖

针对特定任务调整超时:
```bash
# 长任务(代码审查/架构设计)使用5分钟超时
MOKA_TIMEOUT=300 python3 scripts/cli.py dispatch \
    "Review codebase architecture" --backend moka

# 短任务(简单查询)使用1分钟超时
MOKA_TIMEOUT=60 python3 scripts/cli.py dispatch \
    "Explain JWT authentication" --backend moka
```

#### 方法 C: 代码级别覆盖

在 Python 代码中直接指定:
```python
from scripts.collaboration.moka_backend import MokaAIBackend

# 自定义超时5分钟
backend = MokaAIBackend(timeout=300.0)
response = backend.generate("Complex reasoning task...")
```

## 验证配置

检查当前生效的超时配置:
```bash
python3 -c "from scripts.collaboration.moka_backend import MOKA_DEFAULT_TIMEOUT, MOKA_MAX_RETRIES; \
print(f'Default timeout: {MOKA_DEFAULT_TIMEOUT}s'); \
print(f'Max retries: {MOKA_MAX_RETRIES}'); \
print(f'Max wait time: {MOKA_DEFAULT_TIMEOUT * MOKA_MAX_RETRIES}s')"
```

预期输出:
```
Default timeout: 90.0s
Max retries: 2
Max wait time: 180.0s
```

## 故障排查

### 1. 依然超时

如果 180秒 仍然不够,可能原因:
- **本地 Moka 服务性能瓶颈**: 检查 CPU/内存使用率
- **模型加载延迟**: 首次请求可能需要加载模型到内存
- **推理任务过于复杂**: 考虑拆分为多个小任务

解决方案:
```bash
# 临时使用更长超时(10分钟)
export MOKA_TIMEOUT=600

# 或优化 Moka 服务配置(增加工作线程/内存)
# 参考 Moka 服务文档
```

### 2. 验证 Moka 服务健康

快速健康检查:
```bash
# 测试基础连接(应该在5秒内返回)
curl -X POST http://127.0.0.1:8787/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-T6tGOhPri3oXIwduVb4aFm19xxirzxhJ45UHT06G1w7Kl9nG" \
  -d '{
    "model": "moka/claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 10
  }' -w "\nTime: %{time_total}s\n"
```

预期响应时间: < 10秒(正常), > 30秒(需要优化 Moka 服务)

### 3. 监控实际超时

启用调试日志查看实际超时情况:
```bash
export DEVSQUAD_LOG_LEVEL=DEBUG
python3 scripts/cli.py dispatch "task" --backend moka 2>&1 | grep -E "timeout|retry"
```

## 性能优化建议

### 本地 Moka 服务优化

1. **增加工作线程数**:
   ```bash
   # 假设 Moka 服务配置文件
   workers: 4  # 根据 CPU 核心数调整
   ```

2. **预热模型**:
   ```bash
   # 启动后发送空请求预加载模型
   curl -X POST http://127.0.0.1:8787/v1/chat/completions \
     -H "Authorization: Bearer $MOKA_API_KEY" \
     -d '{"model": "moka/claude-sonnet-4-5", "messages": [{"role": "user", "content": "hello"}]}'
   ```

3. **监控资源使用**:
   ```bash
   # 观察 Moka 进程资源占用
   top -pid $(pgrep -f moka) -stats pid,command,cpu,mem
   ```

### DevSquad 任务优化

1. **减少并发角色数**: 串行执行减少 Moka 服务压力
   ```bash
   # 避免: --roles architect security tester coder devops (5角色并发)
   # 推荐: --roles architect security (2-3角色)
   ```

2. **使用缓存**: 相似任务会命中 LLM 缓存,显著降低延迟
   ```bash
   # 首次: 180秒
   # 缓存命中: <1秒
   ```

## 相关文件

- [scripts/collaboration/moka_backend.py](../scripts/collaboration/moka_backend.py): Moka 后端实现
- [scripts/collaboration/constants.py](../scripts/collaboration/constants.py): 全局常量配置
- [moka_ai.json](../moka_ai.json): Moka 服务凭证配置

## 版本历史

- **V4.10.0** (2026-11-05): 
  - 单次超时 30s → 90s
  - 重试次数 3 → 2
  - 支持 `MOKA_TIMEOUT` 环境变量
- **V4.5.2** (初始版本): 
  - 单次超时 30s
  - 重试次数 3

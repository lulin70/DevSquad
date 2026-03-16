# Trae Multi-Agent Skill 安装指南

## 快速安装

### 方法 1：设置环境变量（推荐）

将以下行添加到你的 shell 配置文件（`~/.zshrc` 或 `~/.bashrc`）:

```bash
export TRAE_MULTI_AGENT_SKILL_PATH="$HOME/claw/.trae/skills/trae-multi-agent"
```

然后重新加载配置：

```bash
source ~/.zshrc
```

### 方法 2：创建符号链接（推荐）

```bash
# 创建全局可执行的符号链接
ln -s /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/trae_agent.py /usr/local/bin/trae-agent

# 或者使用 brew link 方式（如果有 brew）
brew link --force trae-multi-agent
```

### 方法 3：使用包装脚本

在任何项目中，直接使用包装脚本的绝对路径：

```bash
python3 /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/trae_agent.py \
  --task "你的任务描述" \
  --agent architect
```

## 使用方法

安装完成后，可以在任何项目目录下直接使用：

```bash
# 调用架构师
trae-agent --task "设计系统架构" --agent architect

# 调用产品经理
trae-agent --task "分析需求" --agent product-manager

# 调用测试专家
trae-agent --task "制定测试策略" --agent test-expert

# 调用独立开发者
trae-agent --task "实现功能" --agent solo-coder
```

## 命令行参数

- `--task`: 任务描述（必需）
- `--agent`: 智能体角色（可选，默认：solo-coder）
  - `architect` - 架构师
  - `product-manager` - 产品经理
  - `test-expert` - 测试专家
  - `solo-coder` - 独立开发者
- `--project-root`: 项目根目录（可选，默认：当前目录）
- `--task-file`: 任务文件路径（可选）
- `--output`: 输出文件路径（可选）
- `--verbose`: 启用详细输出模式
- `--dry-run`: 仅模拟执行，不实际调用智能体

## 验证安装

```bash
# 检查是否能找到 skill
trae-agent --help

# 测试调用
trae-agent --task "测试" --agent architect --dry-run
```

## 故障排查

### 找不到 skill

如果提示 "找不到 trae-multi-agent skill"，请检查：

1. 环境变量是否正确设置：
   ```bash
   echo $TRAE_MULTI_AGENT_SKILL_PATH
   ```

2. skill 路径是否存在：
   ```bash
   ls -la $TRAE_MULTI_AGENT_SKILL_PATH
   ```

3. 重新加载 shell 配置：
   ```bash
   source ~/.zshrc
   ```

### 权限问题

如果遇到权限错误，确保脚本有执行权限：

```bash
chmod +x /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/trae_agent.py
chmod +x /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/trae_agent_dispatch.py
```

## 卸载

```bash
# 如果创建了符号链接
rm /usr/local/bin/trae-agent

# 删除环境变量（从 ~/.zshrc 或 ~/.bashrc 中移除）
unset TRAE_MULTI_AGENT_SKILL_PATH
```

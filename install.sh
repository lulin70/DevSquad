#!/bin/bash
# Trae Multi-Agent Skill 自动安装脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="trae-multi-agent"

echo "🚀 Trae Multi-Agent Skill 安装脚本"
echo "=================================="
echo ""

# 检测 Shell 类型
if [[ -n "$ZSH_VERSION" ]]; then
    SHELL_CONFIG="$HOME/.zshrc"
    SHELL_NAME="zsh"
elif [[ -n "$BASH_VERSION" ]]; then
    SHELL_CONFIG="$HOME/.bashrc"
    SHELL_NAME="bash"
else
    SHELL_CONFIG="$HOME/.profile"
    SHELL_NAME="sh"
fi

echo "📝 检测到 Shell: $SHELL_NAME"
echo "📄 配置文件：$SHELL_CONFIG"
echo ""

# 方法 1: 创建符号链接到 /usr/local/bin
echo "📦 方法 1: 创建全局命令 'trae-agent'"
if [[ -d "/usr/local/bin" ]]; then
    if [[ -L "/usr/local/bin/trae-agent" ]]; then
        echo "   ⚠️  符号链接已存在，正在更新..."
        sudo rm "/usr/local/bin/trae-agent"
    fi
    if sudo ln -s "$SCRIPT_DIR/scripts/trae_agent.py" "/usr/local/bin/trae-agent" 2>/dev/null; then
        echo "   ✅ 已创建符号链接：/usr/local/bin/trae-agent (需要 sudo 权限)"
    else
        echo "   ⚠️  需要 sudo 权限，跳过此方法（可以手动运行：sudo ln -s ...)"
    fi
    echo ""
else
    echo "   ⚠️  /usr/local/bin 不存在，跳过此方法"
    echo ""
fi

# 方法 2: 设置环境变量
echo "📦 方法 2: 设置环境变量 TRAE_MULTI_AGENT_SKILL_PATH"
if grep -q "TRAE_MULTI_AGENT_SKILL_PATH" "$SHELL_CONFIG" 2>/dev/null; then
    echo "   ⚠️  环境变量已存在，正在更新..."
    sed -i.bak '/TRAE_MULTI_AGENT_SKILL_PATH/d' "$SHELL_CONFIG"
fi

echo "export TRAE_MULTI_AGENT_SKILL_PATH=\"$SCRIPT_DIR\"" >> "$SHELL_CONFIG"
echo "   ✅ 已添加到 $SHELL_CONFIG"
echo ""

# 方法 3: 创建别名
echo "📦 方法 3: 创建别名 'trae'"
if grep -q "alias trae=" "$SHELL_CONFIG" 2>/dev/null; then
    echo "   ⚠️  别名已存在，正在更新..."
    sed -i.bak '/alias trae=/d' "$SHELL_CONFIG"
fi

echo "alias trae='python3 \"$SCRIPT_DIR/scripts/trae_agent.py\"'" >> "$SHELL_CONFIG"
echo "   ✅ 已添加到 $SHELL_CONFIG"
echo ""

# 设置执行权限
echo "🔧 设置脚本执行权限..."
chmod +x "$SCRIPT_DIR/scripts/trae_agent.py"
chmod +x "$SCRIPT_DIR/scripts/trae_agent_dispatch.py"
echo "   ✅ 权限已设置"
echo ""

# 验证安装
echo "✅ 安装完成！"
echo ""
echo "📝 使用说明："
echo ""
echo "  1. 重新加载 Shell 配置："
echo "     source $SHELL_CONFIG"
echo ""
echo "  2. 验证安装："
echo "     trae-agent --help"
echo ""
echo "  3. 使用示例："
echo "     trae-agent --task \"你的任务\" --agent architect"
echo ""
echo "  或者使用别名："
echo "     trae --task \"你的任务\" --agent architect"
echo ""
echo "📖 详细文档请查看：$SCRIPT_DIR/INSTALL.md"
echo ""

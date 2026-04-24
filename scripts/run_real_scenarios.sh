#!/bin/bash
# DevSquad 真实场景运行脚本
# 用于生成真实 LLM 输出示例

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== DevSquad 真实场景运行脚本 ===${NC}"
echo ""

# 检查 API 密钥
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${RED}错误: 未设置 API 密钥${NC}"
    echo ""
    echo "请设置以下环境变量之一："
    echo "  export OPENAI_API_KEY='sk-...'"
    echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
    echo ""
    echo "或者创建 .env 文件："
    echo "  cp .env.example .env"
    echo "  # 编辑 .env 添加您的 API 密钥"
    exit 1
fi

# 确定使用的后端
if [ -n "$OPENAI_API_KEY" ]; then
    BACKEND="openai"
    echo -e "${GREEN}使用 OpenAI Backend${NC}"
elif [ -n "$ANTHROPIC_API_KEY" ]; then
    BACKEND="anthropic"
    echo -e "${GREEN}使用 Anthropic Backend${NC}"
fi

# 创建输出目录
OUTPUT_DIR="examples/real_outputs"
mkdir -p "$OUTPUT_DIR"

echo -e "${YELLOW}输出将保存到: $OUTPUT_DIR${NC}"
echo ""

# 场景 1: 架构设计
echo -e "${GREEN}场景 1: 架构设计 (OAuth2 + 2FA)${NC}"
python3 scripts/cli.py dispatch \
  -t "Design a user authentication system with OAuth2 and 2FA support. Include architecture diagram, security considerations, and implementation steps." \
  -r arch sec \
  --backend "$BACKEND" \
  > "$OUTPUT_DIR/scenario1_auth_design.md" 2>&1

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 场景 2: PRD 生成
echo -e "${GREEN}场景 2: PRD 生成 (通知系统)${NC}"
python3 scripts/cli.py dispatch \
  -t "Write a Product Requirements Document (PRD) for a real-time notification system. Include user stories, acceptance criteria, and test strategy." \
  -r pm test \
  --backend "$BACKEND" \
  > "$OUTPUT_DIR/scenario2_notification_prd.md" 2>&1

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 场景 3: 技术选型
echo -e "${GREEN}场景 3: 技术选型 (数据库)NC}"
python3 scripts/cli.py dispatch \
  -t "Compare PostgreSQL vs MongoDB for a high-traffic e-commerce API. Consider scalability, consistency, and operational complexity." \
  -r arch coder \
  --backend "$BACKEND" \
  > "$OUTPUT_DIR/scenario3_database_selection.md" 2>&1

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 场景 4: 安全审计
echo -e "${GREEN}场景 4: 安全审计 (API 端点)${NC}"
python3 scripts/cli.py dispatch \
  -t "Perform a security audit on a REST API with user authentication, file upload, and payment processing endpoints." \
  -r sec test \
  --backend "$BACKEND" \
  > "$OUTPUT_DIR/scenario4_security_audit.md" 2>&1

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 场景 5: UI/UX 设计
echo -e "${GREEN}场景 5: UI/UX 设计 (仪表板)${NC}"
python3 scripts/cli.py dispatch \
  -t "Design a user dashboard for a project management tool. Include wireframes description, interaction flows, and accessibility considerations." \
  -r ui pm \
  --backend "$BACKEND" \
  > "$OUTPUT_DIR/scenario5_dashboard_design.md" 2>&1

echo -e "${GREEN}✓ 完成${NC}"
echo ""

# 生成摘要
echo -e "${GREEN}=== 所有场景运行完成 ===${NC}"
echo ""
echo "输出文件："
ls -lh "$OUTPUT_DIR"
echo ""
echo -e "${YELLOW}下一步:${NC}"
echo "1. 查看输出文件: ls $OUTPUT_DIR"
echo "2. 验证输出质量"
echo "3. 更新 EXAMPLES.md 使用真实输出"
echo ""
echo -e "${GREEN}完成！${NC}"

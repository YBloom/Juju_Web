#!/bin/bash

# ============================================
# Maintenance Mode Toggle Script
# 维护模式切换脚本
# ============================================
#
# 用法：
#   ./scripts/maintenance_toggle.sh on   # 开启维护模式
#   ./scripts/maintenance_toggle.sh off  # 关闭维护模式
#   ./scripts/maintenance_toggle.sh      # 查看当前状态
#
# 功能：
# - 修改 .env 文件中的 MAINTENANCE_MODE 值
# - 支持自动重载 web 服务（uvicorn 热重载）
# ============================================

set -e  # 遇到错误立即退出

# 项目根目录（脚本在 scripts/ 下）
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 检查 .env 文件是否存在
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env 文件不存在于: $ENV_FILE"
        exit 1
    fi
}

# 获取当前维护模式状态
get_current_status() {
    check_env_file
    
    # 读取 MAINTENANCE_MODE 值
    if grep -q "^MAINTENANCE_MODE=" "$ENV_FILE"; then
        MODE_VALUE=$(grep "^MAINTENANCE_MODE=" "$ENV_FILE" | cut -d'=' -f2)
        case "$MODE_VALUE" in
            1|true|True|TRUE|yes|Yes|YES|on|On|ON)
                echo "on"
                ;;
            *)
                echo "off"
                ;;
        esac
    else
        # 如果没有该配置项，默认为关闭
        echo "off"
    fi
}

# 设置维护模式
set_maintenance_mode() {
    local mode=$1
    check_env_file
    
    # 确定新值
    local new_value
    if [ "$mode" = "on" ]; then
        new_value="1"
    else
        new_value="0"
    fi
    
    # 检查是否已存在配置项
    if grep -q "^MAINTENANCE_MODE=" "$ENV_FILE"; then
        # 替换现有值（macOS 和 Linux 兼容的 sed）
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/^MAINTENANCE_MODE=.*/MAINTENANCE_MODE=$new_value/" "$ENV_FILE"
        else
            # Linux
            sed -i "s/^MAINTENANCE_MODE=.*/MAINTENANCE_MODE=$new_value/" "$ENV_FILE"
        fi
    else
        # 追加新配置项
        echo "MAINTENANCE_MODE=$new_value" >> "$ENV_FILE"
    fi
}

# 显示当前状态
show_status() {
    echo ""
    echo "========================================="
    echo "  维护模式状态"
    echo "========================================="
    
    current_status=$(get_current_status)
    
    if [ "$current_status" = "on" ]; then
        print_warning "维护模式: 已开启 🔧"
        echo ""
        print_info "效果："
        echo "  - 普通用户访问网站会看到维护页面"
        echo "  - 管理员请访问 /admin 使用独立账号登录"
        echo "  - 登录后拥有全局访问权限（豁免维护模式）"
    else
        print_success "维护模式: 已关闭 ✨"
        echo ""
        print_info "效果："
        echo "  - 所有用户正常访问网站"
    fi
    
    echo "========================================="
    echo ""
}

# 主逻辑
main() {
    local action=${1:-}
    
    case "$action" in
        on)
            current=$(get_current_status)
            if [ "$current" = "on" ]; then
                print_warning "维护模式已经是开启状态"
                show_status
                exit 0
            fi
            
            print_info "正在开启维护模式..."
            set_maintenance_mode "on"
            print_success "维护模式已开启！"
            echo ""
            print_info "Web 服务将自动重载配置（如果正在运行）"
            print_info "管理员访问: http://your-domain.com/admin （登录后正常使用）"
            show_status
            ;;
        
        off)
            current=$(get_current_status)
            if [ "$current" = "off" ]; then
                print_warning "维护模式已经是关闭状态"
                show_status
                exit 0
            fi
            
            print_info "正在关闭维护模式..."
            set_maintenance_mode "off"
            print_success "维护模式已关闭！"
            echo ""
            print_info "Web 服务将自动重载配置（如果正在运行）"
            print_info "网站已恢复正常访问"
            show_status
            ;;
        
        status|"")
            # 无参数或 status：显示当前状态
            show_status
            ;;
        
        *)
            print_error "未知命令: $action"
            echo ""
            echo "用法："
            echo "  $0 on      # 开启维护模式"
            echo "  $0 off     # 关闭维护模式"
            echo "  $0 status  # 查看当前状态（默认）"
            exit 1
            ;;
    esac
}

# 运行主逻辑
main "$@"

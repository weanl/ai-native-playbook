# NextAIOpsAlgoApp Makefile
# M0 Walking Skeleton

.PHONY: dev test lint fmt smoke demo clean help

# 默认目标
.DEFAULT_GOAL := help

# 变量定义
PYTHON := python3
PYTEST := pytest
RUFF := ruff
MYPY := mypy
STREAMLIT := streamlit

SRC_DIR := src/nextaiops_algo
TEST_DIR := tests

# ALG 参数用于冒烟测试（默认为空，表示跑所有算法）
ALG ?= ""

# =============================================================================
# 开发环境
# =============================================================================

dev: ## 启动开发环境（docker compose）
	docker compose up -d

dev-down: ## 停止开发环境
	docker compose down

dev-build: ## 构建开发环境镜像
	docker compose build

# =============================================================================
# 测试
# =============================================================================

test: ## 运行所有测试（unit + integration + smoke）
	$(PYTEST) $(TEST_DIR) -v

test-unit: ## 仅运行单元测试
	$(PYTEST) $(TEST_DIR)/unit -v

test-integration: ## 仅运行集成测试
	$(PYTEST) $(TEST_DIR)/integration -v

# =============================================================================
# 冒烟实验
# =============================================================================

smoke: ## 运行冒烟测试（ALG 参数可选，如 make smoke ALG=three_sigma）
ifneq ($(ALG),"")
	$(PYTEST) $(TEST_DIR)/smoke -v -k $(ALG)
else
	$(PYTEST) $(TEST_DIR)/smoke -v
endif

# =============================================================================
# 代码质量
# =============================================================================

lint: ## 运行静态检查（ruff + mypy --strict）
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	$(MYPY) --strict $(SRC_DIR)

fmt: ## 格式化代码（ruff format）
	$(RUFF) format $(SRC_DIR) $(TEST_DIR)

fmt-check: ## 检查格式（不修改文件）
	$(RUFF) format --check $(SRC_DIR) $(TEST_DIR)

# =============================================================================
# Demo
# =============================================================================

demo: ## 启动 Streamlit demo
	$(STREAMLIT) run $(SRC_DIR)/ui/app.py

# =============================================================================
# 安装与清理
# =============================================================================

install: ## 安装项目（开发模式）
	$(PYTHON) -m pip install -e ".[dev]"

clean: ## 清理缓存和临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .nextaiops_algo 2>/dev/null || true

# =============================================================================
# 帮助
# =============================================================================

help: ## 显示帮助信息
	@echo "NextAIOpsAlgoApp - M0 Walking Skeleton"
	@echo ""
	@echo "常用命令:"
	@echo "  make dev          启动开发环境（docker compose）"
	@echo "  make test         运行所有测试"
	@echo "  make lint         静态检查（ruff + mypy）"
	@echo "  make fmt          格式化代码"
	@echo "  make smoke ALG=X  冒烟测试（指定算法）"
	@echo "  make demo         启动 Streamlit demo"
	@echo ""
	@echo "完整命令列表:"
	@grep -E '^([a-zA-Z_-]+):.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
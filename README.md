# Riemann

用大模型+Lean代码的逻辑化证明来帮数学工作者指导科研工作的开源AI Agent。

## 项目简介

Riemann 是一个基于大语言模型和 Lean 代码的形式化证明系统，旨在帮助数学工作者进行科研工作。通过结合先进的AI技术和严格的数学证明验证，Riemann 能够：

- 协助数学定理的形式化证明
- 验证数学推导的严格性
- 为数学研究提供智能辅助

## 系统架构

```
用户输入定理
    ↓
LLM生成数学证明
    ↓
证明转Lean代码
    ↓
Lean API验证
    ↓
┌─ 正确 → 输出给用户
│
└─ 错误 → 分析错误类型
          ├─ 代码层面错误 → 修正代码细节
          └─ 证明思路错误 → 重新思考证明
          ↓
      重新验证 (最多10次迭代)
```

## 项目结构

```
src/
├── agent/              # Agent核心模块
│   ├── proof_generator.py    # LLM生成证明
│   ├── proof_to_lean.py      # 证明转Lean代码
│   ├── verification_loop.py   # 验证循环控制器
│   └── state.py              # 状态机
├── llm_module/         # LLM接口模块
│   ├── anthropic_client.py    # Anthropic Claude
│   ├── openai_client.py       # OpenAI GPT
│   └── client.py              # 基类和工厂
├── lean_api/           # Lean验证模块
│   ├── client.py             # API客户端
│   ├── exceptions.py         # 异常定义
│   └── models.py             # 数据模型
├── cli/                # CLI界面
└── main.py             # 程序入口
```

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 配置环境变量

创建 `.env` 文件或设置环境变量：

```bash
# Anthropic API (推荐)
export ANTHROPIC_API_KEY=sk-ant-...

# 或使用 OpenAI
export OPENAI_API_KEY=sk-...
```

### 3. 运行

```bash
# 命令行模式
python -m src.main "forall n : Nat, n + 0 = n"

# 交互模式
python -m src.main
```

## API服务

- **Mathhammer** (推荐) - 专为数学验证设计的免费API
- **Local Lean 4** - 本地部署，完全免费

## 技术栈

- 大语言模型 (LLM)
- Lean 4 形式化证明语言
- Python

## 许可证

MIT License

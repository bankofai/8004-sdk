#!/usr/bin/env python3
"""
TRC-8004 CLI 工具

提供快速创建 Agent 项目的脚手架命令。

使用方式:
    trc8004 init my-agent          # 创建新 Agent 项目
    trc8004 init my-agent --port 8200
    trc8004 register               # 注册 Agent 到链上
    trc8004 test                   # 测试 Agent 连通性
"""

import argparse
import os
import sys
from pathlib import Path


# ============ 模板定义 ============

AGENT_TEMPLATE = '''#!/usr/bin/env python3
"""
{name} - 基于 TRC-8004 框架的 Agent

启动:
    python app.py

测试:
    curl http://localhost:{port}/.well-known/agent-card.json
"""

import json
import os
import time
import uuid
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from agent_protocol import Agent, Step, Task, router

# ============ 配置 ============

AGENT_NAME = os.getenv("AGENT_NAME", "{name}")
AGENT_PORT = int(os.getenv("AGENT_PORT", "{port}"))
PAYMENT_ADDRESS = os.getenv("PAYMENT_ADDRESS", "TYourPaymentAddress")


# ============ Agent 实例 ============

agent = Agent()


def _normalize_input(value: Any) -> Dict[str, Any]:
    """规范化输入"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {{"text": value}}
    return {{}}


# ============ Agent Card ============

AGENT_CARD = {{
    "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
    "name": AGENT_NAME,
    "description": "{description}",
    "version": "0.1.0",
    "url": f"http://localhost:{{AGENT_PORT}}",
    "endpoints": [
        {{"name": "A2A", "endpoint": f"http://localhost:{{AGENT_PORT}}", "version": "0.3.0"}},
        {{"name": "agentWallet", "endpoint": f"eip155:1:{{PAYMENT_ADDRESS}}"}}
    ],
    "capabilities": {{"streaming": False, "pushNotifications": False}},
    "defaultInputModes": ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {{
            "id": "hello",
            "name": "Say Hello",
            "description": "返回问候消息",
            "inputSchema": {{
                "type": "object",
                "properties": {{"name": {{"type": "string"}}}},
            }}
        }},
        {{
            "id": "echo",
            "name": "Echo Message",
            "description": "回显输入消息",
            "inputSchema": {{
                "type": "object",
                "properties": {{"message": {{"type": "string"}}}},
                "required": ["message"]
            }}
        }}
    ],
    "tags": {tags}
}}


# ============ REST Endpoints ============

@router.get("/.well-known/agent-card.json")
def agent_card() -> JSONResponse:
    return JSONResponse(content=AGENT_CARD)


@router.get("/health")
def health() -> JSONResponse:
    return JSONResponse(content={{"status": "healthy", "agent": AGENT_NAME}})


# ============ A2A Handlers ============

async def task_handler(task: Task) -> None:
    print(f"📥 Task created: {{task.task_id}}")
    await Agent.db.create_step(task_id=task.task_id)


async def step_handler(step: Step) -> Step:
    payload = _normalize_input(step.input)
    skill = payload.get("skill") or payload.get("action")
    args = payload.get("args", payload)
    
    # ========== 在这里添加你的技能 ==========
    
    if skill == "hello":
        name = args.get("name", "World")
        result = {{"message": f"Hello, {{name}}!", "timestamp": int(time.time())}}
        step.output = json.dumps(result, ensure_ascii=False)
        step.is_last = True
        return step
    
    if skill == "echo":
        message = args.get("message", "")
        result = {{"echo": message, "length": len(message)}}
        step.output = json.dumps(result, ensure_ascii=False)
        step.is_last = True
        return step
    
    # 默认响应
    result = {{
        "error": "UNKNOWN_SKILL" if skill else "NO_SKILL",
        "available": ["hello", "echo"],
        "usage": {{"skill": "hello", "args": {{"name": "Alice"}}}}
    }}
    step.output = json.dumps(result, ensure_ascii=False)
    step.is_last = True
    return step


Agent.setup_agent(task_handler, step_handler)


if __name__ == "__main__":
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║  {name:^53} ║
╠═══════════════════════════════════════════════════════════╣
║  Port: {{AGENT_PORT}}                                            ║
║  Card: http://localhost:{{AGENT_PORT}}/.well-known/agent-card.json
╚═══════════════════════════════════════════════════════════╝
""")
    Agent.start(port=AGENT_PORT, router=router)
'''

PYPROJECT_TEMPLATE = '''[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "agent-protocol>=1.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
sdk = ["trc-8004-sdk"]
test = ["pytest>=8.0.0"]

[tool.uv]
package = true

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
'''

ENV_TEMPLATE = '''# Agent 配置
AGENT_NAME={name}
AGENT_PORT={port}
PAYMENT_ADDRESS=TYourPaymentAddress

# TRC-8004 SDK 配置 (可选)
# TRON_RPC_URL=https://nile.trongrid.io
# TRON_PRIVATE_KEY=your_hex_private_key
# IDENTITY_REGISTRY=TIdentityRegistryAddress
# VALIDATION_REGISTRY=TValidationRegistryAddress
# REPUTATION_REGISTRY=TReputationRegistryAddress

# Central Service (可选)
# CENTRAL_SERVICE_URL=http://localhost:8001
'''

README_TEMPLATE = '''# {name}

基于 TRC-8004 框架的 Agent。

## 快速开始

```bash
# 安装依赖
uv sync  # 或 pip install -e .

# 启动 Agent
python app.py

# 测试
curl http://localhost:{port}/.well-known/agent-card.json
```

## 技能列表

| 技能 ID | 名称 | 描述 |
|---------|------|------|
| `hello` | Say Hello | 返回问候消息 |
| `echo` | Echo Message | 回显输入消息 |

## 调用示例

```bash
# 1. 创建任务
curl -X POST http://localhost:{port}/ap/v1/agent/tasks \\
  -H "Content-Type: application/json" \\
  -d '{{"input": {{"skill": "hello", "args": {{"name": "Alice"}}}}}}'

# 2. 执行步骤 (使用返回的 task_id)
curl -X POST http://localhost:{port}/ap/v1/agent/tasks/TASK_ID/steps \\
  -H "Content-Type: application/json" \\
  -d '{{}}'
```

## 添加新技能

编辑 `app.py` 中的 `step_handler` 函数:

```python
if skill == "my_new_skill":
    # 你的逻辑
    result = {{"data": "..."}}
    step.output = json.dumps(result)
    step.is_last = True
    return step
```

然后在 `AGENT_CARD["skills"]` 中添加技能声明。

## 注册到 Central Service

```bash
curl -X POST http://localhost:8001/admin/agents \\
  -H "Content-Type: application/json" \\
  -d '{{
    "address": "{name_lower}",
    "name": "{name}",
    "url": "http://localhost:{port}",
    "tags": {tags}
  }}'
```

## 链上注册 (可选)

```python
from sdk import AgentSDK

sdk = AgentSDK(private_key="...", identity_registry="...")
tx_id = sdk.register_agent(token_uri="https://your-domain/{name_lower}.json")
```
'''

TEST_TEMPLATE = '''"""
{name} 单元测试
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_agent_card(client):
    resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "{name}"
    assert "skills" in data


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
'''

GITIGNORE_TEMPLATE = '''__pycache__/
*.py[cod]
.venv/
.env
*.db
*.log
.pytest_cache/
'''


# ============ CLI 命令 ============

def cmd_init(args):
    """初始化新 Agent 项目"""
    name = args.name
    port = args.port
    tags = args.tags.split(",") if args.tags else ["custom"]
    description = args.description or f"{name} - TRC-8004 Agent"
    
    # 创建目录
    project_dir = Path(name.lower().replace(" ", "-").replace("_", "-"))
    if project_dir.exists():
        print(f"❌ 目录已存在: {project_dir}")
        return 1
    
    project_dir.mkdir(parents=True)
    tests_dir = project_dir / "tests"
    tests_dir.mkdir()
    
    # 生成文件
    files = {
        "app.py": AGENT_TEMPLATE.format(
            name=name, port=port, description=description, tags=tags
        ),
        "pyproject.toml": PYPROJECT_TEMPLATE.format(
            name=name.lower().replace(" ", "-"), description=description
        ),
        ".env.example": ENV_TEMPLATE.format(name=name, port=port),
        "README.md": README_TEMPLATE.format(
            name=name, port=port, tags=tags, name_lower=name.lower().replace(" ", "-")
        ),
        ".gitignore": GITIGNORE_TEMPLATE,
        "tests/__init__.py": "",
        "tests/test_agent.py": TEST_TEMPLATE.format(name=name),
    }
    
    for filename, content in files.items():
        filepath = project_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    
    print(f"""
✅ Agent 项目创建成功!

📁 {project_dir}/
   ├── app.py           # Agent 主程序
   ├── pyproject.toml   # 项目配置
   ├── .env.example     # 环境变量模板
   ├── README.md        # 文档
   └── tests/           # 测试

🚀 下一步:
   cd {project_dir}
   cp .env.example .env
   uv sync              # 或 pip install -e .
   python app.py

📖 文档: {project_dir}/README.md
""")
    return 0


def cmd_test(args):
    """测试 Agent 连通性"""
    import urllib.request
    import json as json_module
    
    url = args.url.rstrip("/")
    
    print(f"🔍 测试 Agent: {url}")
    
    # 测试 agent-card
    try:
        card_url = f"{url}/.well-known/agent-card.json"
        with urllib.request.urlopen(card_url, timeout=5) as resp:
            card = json_module.loads(resp.read())
        print(f"✅ Agent Card: {card.get('name', 'Unknown')}")
        print(f"   Skills: {[s['id'] for s in card.get('skills', [])]}")
        print(f"   Tags: {card.get('tags', [])}")
    except Exception as e:
        print(f"❌ Agent Card 获取失败: {e}")
        return 1
    
    # 测试 health
    try:
        health_url = f"{url}/health"
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            health = json_module.loads(resp.read())
        print(f"✅ Health: {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"⚠️  Health 端点不可用: {e}")
    
    print("\n✅ Agent 连通性测试通过!")
    return 0


def cmd_register(args):
    """注册 Agent 到链上"""
    import json as json_module
    
    print("🔗 注册 Agent 到链上...")
    
    # 检查环境变量
    required = ["TRON_PRIVATE_KEY", "IDENTITY_REGISTRY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        print("\n请设置以下环境变量:")
        print("  export TRON_PRIVATE_KEY=your_hex_private_key")
        print("  export IDENTITY_REGISTRY=TIdentityRegistryAddress")
        return 1
    
    try:
        from sdk import AgentSDK
    except ImportError:
        print("❌ 请先安装 SDK: pip install trc-8004-sdk")
        return 1
    
    sdk = AgentSDK(
        private_key=os.getenv("TRON_PRIVATE_KEY"),
        rpc_url=os.getenv("TRON_RPC_URL", "https://nile.trongrid.io"),
        network=os.getenv("TRON_NETWORK", "tron:nile"),
        identity_registry=os.getenv("IDENTITY_REGISTRY"),
    )
    
    # 加载 metadata
    metadata = None
    
    # 优先从 agent-card.json 加载
    if args.card:
        card_path = Path(args.card)
        if not card_path.exists():
            print(f"❌ Agent Card 文件不存在: {card_path}")
            return 1
        try:
            with open(card_path) as f:
                card = json_module.load(f)
            metadata = AgentSDK.extract_metadata_from_card(card)
            print(f"📋 从 Agent Card 提取 metadata:")
            for m in metadata:
                value_preview = m["value"][:50] + "..." if len(m["value"]) > 50 else m["value"]
                print(f"   - {m['key']}: {value_preview}")
        except Exception as e:
            print(f"❌ 解析 Agent Card 失败: {e}")
            return 1
    elif args.metadata:
        # 从 JSON 字符串加载
        try:
            raw = json_module.loads(args.metadata)
            if isinstance(raw, dict):
                metadata = [{"key": k, "value": v} for k, v in raw.items()]
            elif isinstance(raw, list):
                metadata = raw
            print(f"📋 使用自定义 metadata: {[m['key'] for m in metadata]}")
        except Exception as e:
            print(f"❌ 解析 metadata JSON 失败: {e}")
            return 1
    elif args.name:
        # 简单模式：只设置 name
        metadata = [{"key": "name", "value": args.name}]
        print(f"📋 使用简单 metadata: name={args.name}")
    
    try:
        tx_id = sdk.register_agent(
            token_uri=args.token_uri or "",
            metadata=metadata,
        )
        print(f"\n✅ 注册成功!")
        print(f"   交易 ID: {tx_id}")
        if metadata:
            print(f"   Metadata 数量: {len(metadata)}")
    except Exception as e:
        print(f"❌ 注册失败: {e}")
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="trc8004",
        description="TRC-8004 CLI 工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # init 命令
    init_parser = subparsers.add_parser("init", help="创建新 Agent 项目")
    init_parser.add_argument("name", help="Agent 名称")
    init_parser.add_argument("--port", "-p", type=int, default=8100, help="端口号 (默认 8100)")
    init_parser.add_argument("--tags", "-t", help="标签，逗号分隔 (默认 custom)")
    init_parser.add_argument("--description", "-d", help="Agent 描述")
    
    # test 命令
    test_parser = subparsers.add_parser("test", help="测试 Agent 连通性")
    test_parser.add_argument("--url", "-u", default="http://localhost:8100", help="Agent URL")
    
    # register 命令
    reg_parser = subparsers.add_parser("register", help="注册 Agent 到链上")
    reg_parser.add_argument("--token-uri", "-t", help="Token URI (可选)")
    reg_parser.add_argument("--card", "-c", help="Agent Card JSON 文件路径 (自动提取 metadata)")
    reg_parser.add_argument("--metadata", "-m", help="Metadata JSON 字符串")
    reg_parser.add_argument("--name", "-n", help="Agent 名称 (简单模式)")
    
    args = parser.parse_args()
    
    if args.command == "init":
        return cmd_init(args)
    elif args.command == "test":
        return cmd_test(args)
    elif args.command == "register":
        return cmd_register(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

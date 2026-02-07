#!/usr/bin/env python3
"""
TRON-8004 CLI Tool

Provides scaffolding commands for quickly creating Agent projects.

Usage:
    tron8004 init my-agent          # Create a new Agent project
    tron8004 init my-agent --port 8200
    tron8004 register               # Register Agent on-chain
    tron8004 test                   # Test Agent connectivity
"""

import argparse
import os
import sys
from pathlib import Path


# ============ Template Definitions ============

AGENT_TEMPLATE = '''#!/usr/bin/env python3
"""
{name} - Agent based on TRON-8004 Framework

Start:
    python app.py

Test:
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

# ============ Configuration ============

AGENT_NAME = os.getenv("AGENT_NAME", "{name}")
AGENT_PORT = int(os.getenv("AGENT_PORT", "{port}"))
PAYMENT_ADDRESS = os.getenv("PAYMENT_ADDRESS", "TYourPaymentAddress")


# ============ Agent Instance ============

agent = Agent()


def _normalize_input(value: Any) -> Dict[str, Any]:
    """Normalize input"""
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
            "description": "Returns a greeting message",
            "inputSchema": {{
                "type": "object",
                "properties": {{"name": {{"type": "string"}}}},
            }}
        }},
        {{
            "id": "echo",
            "name": "Echo Message",
            "description": "Echoes the input message",
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
    
    # ========== Add your skills here ==========
    
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
    
    # Default response
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
sdk = ["tron-8004-sdk"]
test = ["pytest>=8.0.0"]

[tool.uv]
package = true

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
'''

ENV_TEMPLATE = '''# Agent Configuration
AGENT_NAME={name}
AGENT_PORT={port}
PAYMENT_ADDRESS=TYourPaymentAddress

# TRON-8004 SDK Configuration (Optional)
# TRON_RPC_URL=https://nile.trongrid.io
# TRON_PRIVATE_KEY=your_hex_private_key
# IDENTITY_REGISTRY=TIdentityRegistryAddress
# VALIDATION_REGISTRY=TValidationRegistryAddress
# REPUTATION_REGISTRY=TReputationRegistryAddress

# Central Service (Optional)
# CENTRAL_SERVICE_URL=http://localhost:8001
'''

README_TEMPLATE = '''# {name}

Agent based on the TRON-8004 Framework.

## Quick Start

```bash
# Install dependencies
uv sync  # or pip install -e .

# Start Agent
python app.py

# Test
curl http://localhost:{port}/.well-known/agent-card.json
```

## Skills

| Skill ID | Name | Description |
|---------|------|------|
| `hello` | Say Hello | Returns a greeting message |
| `echo` | Echo Message | Echoes the input message |

## Usage Examples

```bash
# 1. Create task
curl -X POST http://localhost:{port}/ap/v1/agent/tasks \\
  -H "Content-Type: application/json" \\
  -d '{{"input": {{"skill": "hello", "args": {{"name": "Alice"}}}}}}'

# 2. Execute step (use the returned task_id)
curl -X POST http://localhost:{port}/ap/v1/agent/tasks/TASK_ID/steps \\
  -H "Content-Type: application/json" \\
  -d '{{}}'
```

## Adding New Skills

Edit the `step_handler` function in `app.py`:

```python
if skill == "my_new_skill":
    # Your logic
    result = {{"data": "..."}}
    step.output = json.dumps(result)
    step.is_last = True
    return step
```

Then add the skill declaration in `AGENT_CARD["skills"]`.

## Register with Central Service

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

## On-chain Registration (Optional)

```python
from sdk import AgentSDK

sdk = AgentSDK(private_key="...", identity_registry="...")
tx_id = sdk.register_agent(token_uri="https://your-domain/{name_lower}.json")
```
'''

TEST_TEMPLATE = '''"""
{name} Unit Tests
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


# ============ CLI Commands ============

def cmd_init(args):
    """Initialize a new Agent project"""
    name = args.name
    port = args.port
    tags = args.tags.split(",") if args.tags else ["custom"]
    description = args.description or f"{name} - TRON-8004 Agent"
    
    # Create directory
    project_dir = Path(name.lower().replace(" ", "-").replace("_", "-"))
    if project_dir.exists():
        print(f"❌ Directory already exists: {project_dir}")
        return 1
    
    project_dir.mkdir(parents=True)
    tests_dir = project_dir / "tests"
    tests_dir.mkdir()
    
    # Generate files
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
✅ Agent project created successfully!

📁 {project_dir}/
   ├── app.py           # Agent Main Program
   ├── pyproject.toml   # Project Config
   ├── .env.example     # Env Var Template
   ├── README.md        # Documentation
   └── tests/           # Tests

🚀 Next Steps:
   cd {project_dir}
   cp .env.example .env
   uv sync              # or pip install -e .
   python app.py

📖 Documentation: {project_dir}/README.md
""")
    return 0


def cmd_test(args):
    """Test Agent connectivity"""
    import urllib.request
    import json as json_module
    
    url = args.url.rstrip("/")
    
    print(f"🔍 Testing Agent: {url}")
    
    # Test agent-card
    try:
        card_url = f"{url}/.well-known/agent-card.json"
        with urllib.request.urlopen(card_url, timeout=5) as resp:
            card = json_module.loads(resp.read())
        print(f"✅ Agent Card: {card.get('name', 'Unknown')}")
        print(f"   Skills: {[s['id'] for s in card.get('skills', [])]}")
        print(f"   Tags: {card.get('tags', [])}")
    except Exception as e:
        print(f"❌ Failed to get Agent Card: {e}")
        return 1
    
    # Test health
    try:
        health_url = f"{url}/health"
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            health = json_module.loads(resp.read())
        print(f"✅ Health: {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"⚠️  Health endpoint unavailable: {e}")
    
    print("\n✅ Agent connectivity test passed!")
    return 0


def cmd_register(args):
    """Register Agent on-chain"""
    import json as json_module
    
    print("🔗 Registering Agent on-chain...")
    
    # Check environment variables
    required = ["TRON_PRIVATE_KEY", "IDENTITY_REGISTRY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("\nPlease set the following environment variables:")
        print("  export TRON_PRIVATE_KEY=your_hex_private_key")
        print("  export IDENTITY_REGISTRY=TIdentityRegistryAddress")
        return 1
    
    try:
        from sdk import AgentSDK
    except ImportError:
        print("❌ Please install SDK first: pip install tron-8004-sdk")
        return 1
    
    sdk = AgentSDK(
        private_key=os.getenv("TRON_PRIVATE_KEY"),
        rpc_url=os.getenv("TRON_RPC_URL", "https://nile.trongrid.io"),
        network=os.getenv("TRON_NETWORK", "tron:nile"),
        identity_registry=os.getenv("IDENTITY_REGISTRY"),
    )
    
    # Load metadata
    metadata = None
    
    # Prefer loading from agent-card.json
    if args.card:
        card_path = Path(args.card)
        if not card_path.exists():
            print(f"❌ Agent Card file not found: {card_path}")
            return 1
        try:
            with open(card_path) as f:
                card = json_module.load(f)
            metadata = AgentSDK.extract_metadata_from_card(card)
            print(f"📋 Extracted metadata from Agent Card:")
            for m in metadata:
                value_preview = m["value"][:50] + "..." if len(m["value"]) > 50 else m["value"]
                print(f"   - {m['key']}: {value_preview}")
        except Exception as e:
            print(f"❌ Failed to parse Agent Card: {e}")
            return 1
    elif args.metadata:
        # Load from JSON string
        try:
            raw = json_module.loads(args.metadata)
            if isinstance(raw, dict):
                metadata = [{"key": k, "value": v} for k, v in raw.items()]
            elif isinstance(raw, list):
                metadata = raw
            print(f"📋 Using custom metadata: {[m['key'] for m in metadata]}")
        except Exception as e:
            print(f"❌ Failed to parse metadata JSON: {e}")
            return 1
    elif args.name:
        # Simple mode: only set name
        metadata = [{"key": "name", "value": args.name}]
        print(f"📋 Using simple metadata: name={args.name}")
    
    try:
        tx_id = sdk.register_agent(
            token_uri=args.token_uri or "",
            metadata=metadata,
        )
        print(f"\n✅ Registered successfully!")
        print(f"   Transaction ID: {tx_id}")
        if metadata:
            print(f"   Metadata count: {len(metadata)}")
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="tron8004",
        description="TRON-8004 CLI Tool",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Create new Agent project")
    init_parser.add_argument("name", help="Agent Name")
    init_parser.add_argument("--port", "-p", type=int, default=8100, help="Port number (default 8100)")
    init_parser.add_argument("--tags", "-t", help="Tags, comma separated (default custom)")
    init_parser.add_argument("--description", "-d", help="Agent Description")
    
    # test command
    test_parser = subparsers.add_parser("test", help="Test Agent connectivity")
    test_parser.add_argument("--url", "-u", default="http://localhost:8100", help="Agent URL")
    
    # register command
    reg_parser = subparsers.add_parser("register", help="Register Agent on-chain")
    reg_parser.add_argument("--token-uri", "-t", help="Token URI (optional)")
    reg_parser.add_argument("--card", "-c", help="Agent Card JSON file path (auto-extract metadata)")
    reg_parser.add_argument("--metadata", "-m", help="Metadata JSON string")
    reg_parser.add_argument("--name", "-n", help="Agent Name (simple mode)")
    
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

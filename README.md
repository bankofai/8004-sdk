# 8004-sdk

Monorepo for ERC/TRC-8004 SDKs.
Current layout includes a Python SDK and a TypeScript SDK.

## Repository Structure

- `python/`: Python SDK (`bankofai.erc_8004`)
- `ts/`: TypeScript SDK (`@bankofai/8004-sdk`)

## Python SDK

Location:
- `python/`

Entrypoint:
- `from bankofai.erc_8004.core.sdk import SDK`

Install (local editable):

```bash
cd python
pip install -e .
```

Quick run:

```bash
python sample/bsc_register.py
python sample/tron_register.py
```

More docs:
- `python/README.md`
- `python/sample/README.md`

## TypeScript SDK

Location:
- `ts/`

Entrypoint:
- `import { SDK } from "@bankofai/8004-sdk"`

Install and build (local):

```bash
cd ts
npm install
npm run build
```

Quick run:

```bash
npx tsx examples/register-bsc.ts
npx tsx examples/register-tron.ts
```

More docs:
- `ts/README.md`
- `ts/examples/README.md`

## Subgraph Status

Subgraph URL integration is not supported in the current release.
It is planned for a future update.

# tron-8004-sdk

Monorepo-style layout for multi-language SDKs.

## Structure

- `python/`: Python SDK
- `ts/`: TypeScript SDK (MVP scaffold)

## Quick Start

### Python

```bash
cd python
pip install -e .
python sample/bsc_register.py
python sample/tron_register.py
```

### TypeScript

```bash
cd ts
npm install
npm run build
npx tsx examples/register-bsc.ts
npx tsx examples/register-tron.ts
```

See `python/README.md` and `ts/README.md` for full usage and samples.

## Subgraph Status

Subgraph URL integration is not supported in the current release.
It is planned for a future update.

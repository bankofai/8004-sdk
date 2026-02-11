# Samples

Run from the `python/` directory after editable install:

```bash
pip install -e .
```

All sample scripts create a fully configured agent (name/description/image, MCP, A2A, skills, domains, trust, metadata, active, and x402 support) before `register()`.

## TRON register

```bash
python sample/tron_register.py
```

Edit `TRON_NETWORK`, `TRON_RPC_URL`, `TRON_PRIVATE_KEY`, and `TRON_FEE_LIMIT` in `sample/tron_register.py` before running.

## BSC testnet register

```bash
python sample/bsc_register.py
```

Edit `BSC_PRIVATE_KEY` in `sample/bsc_register.py` before running.

## BSC reputation flow

```bash
python sample/bsc_reputation_flow.py
```

Edit `OWNER_PRIVATE_KEY` and `REVIEWER_PRIVATE_KEY` in `sample/bsc_reputation_flow.py` before running.

## TRON reputation flow

```bash
python sample/tron_reputation_flow.py
```

Edit `TRON_NETWORK`, `TRON_RPC_URL`, `TRON_FEE_LIMIT`, `OWNER_PRIVATE_KEY`, and `REVIEWER_PRIVATE_KEY` in `sample/tron_reputation_flow.py` before running.

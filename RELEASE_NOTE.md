# Release v1.1.1

The **BankOfAI 8004 SDK v1.1.1** is a maintenance release focusing on packaging fixes for the TypeScript SDK and CI/CD improvements.

## 🚀 What's New

### 🛠 Fixed & Improved
- **TypeScript Packaging Fix**: Resolved a critical issue where the `resource/` directory (containing ABIs and chain configs) was missing from the published npm package.
- **CI/CD Enhancements**: Improved GitHub Actions workflows for more reliable builds and testing across Python and TypeScript environments.
- **SDK Synchronization**: Version parity maintained across `@bankofai/8004-sdk` (NPM) and `bankofai-8004-sdk` (PyPI).

## 📦 Installation

### TypeScript
```bash
npm install @bankofai/8004-sdk@1.1.1
```

### Python
```bash
pip install bankofai-8004-sdk==1.1.1
```

## 🛠 Developer Resources
- **Changelog**: See [CHANGELOG.md](./CHANGELOG.md) for a detailed list of changes.
- **Examples**: Full usage samples are available in `ts/examples/` and `python/sample/`.

---
**Full Changelog**: https://github.com/bankofai/8004-sdk/compare/v1.1.0...v1.1.1

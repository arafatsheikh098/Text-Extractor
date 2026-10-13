# Contributing to Text Extractor

Thank you for your interest in contributing to Text Extractor! This document outlines our development workflow and contribution process.

## Code of Conduct

Please maintain a welcoming, respectful, and constructive environment for all participants.

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork**:
   ```bash
   git clone https://github.com/<your-username>/Text_extractor.git
   cd Text_extractor
   ```
3. **Set up a Python virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
4. **Install development dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

## Running Tests and Quality Checks

Before submitting a Pull Request, ensure that all tests and linting checks pass:

```bash
# Run unit and integration tests
pytest

# Run tests with coverage summary
pytest --cov=text_extractor --cov-report=term-missing

# Check code formatting and linting
ruff check src tests
```

## Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Write clean, typed, and well-commented Python code.
3. Write corresponding tests in `tests/`.
4. Commit your changes with clear, descriptive commit messages.
5. Push to your branch and open a Pull Request against `main`.

## Licensing Notice

By contributing to Text Extractor, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

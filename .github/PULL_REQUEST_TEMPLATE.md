## Description

<!-- Brief description of what this PR changes and why -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Refactoring (code changes that neither fix a bug nor add a feature)
- [ ] Documentation update
- [ ] Test improvement
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)

## Testing

- [ ] Tests pass locally (`pytest tests/ -q --tb=short -m "not slow"`)
- [ ] Lint passes (`ruff check scripts/ skills/ --ignore=E501,W291`)
- [ ] Type check passes (`mypy scripts/collaboration/ --ignore-missing-imports --no-error-summary`)
- [ ] Security scan passes (`bandit -r scripts/ -c pyproject.toml -ll`)

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or my feature works

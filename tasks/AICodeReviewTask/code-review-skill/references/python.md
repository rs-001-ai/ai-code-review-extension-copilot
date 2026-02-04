# Python Code Review

Python-specific best practices and patterns.

## Table of Contents
1. [Style & Conventions](#style--conventions)
2. [Type Hints](#type-hints)
3. [Common Pitfalls](#common-pitfalls)
4. [Async Python](#async-python)
5. [Testing](#testing)
6. [Package Structure](#package-structure)

---

## Style & Conventions

### PEP 8 Essentials

```python
# Naming conventions
variable_name = "snake_case"
CONSTANT_NAME = "UPPER_SNAKE"
ClassName = "PascalCase"
_private_var = "leading underscore"
__name_mangled = "double underscore"

# Imports order (isort)
# 1. Standard library
import os
import sys

# 2. Third-party
import requests
from fastapi import FastAPI

# 3. Local
from myapp.models import User
```

### Pythonic Code

```python
# BAD - Non-pythonic
if len(items) > 0:
    pass
if x == True:
    pass
if x == None:
    pass

# GOOD - Pythonic
if items:
    pass
if x:
    pass
if x is None:
    pass
```

```python
# BAD - Manual iteration
result = []
for item in items:
    if item.active:
        result.append(item.name)

# GOOD - List comprehension
result = [item.name for item in items if item.active]
```

```python
# BAD - Manual dictionary building
d = {}
for item in items:
    d[item.id] = item

# GOOD - Dict comprehension
d = {item.id: item for item in items}
```

**Review Checklist:**
- [ ] Follows PEP 8 naming conventions
- [ ] Uses comprehensions appropriately
- [ ] Truthiness checks instead of explicit comparisons
- [ ] `is` for None/True/False comparisons
- [ ] Imports organized (standard, third-party, local)

---

## Type Hints

### Modern Type Annotations (Python 3.10+)

```python
# Basic types
def greet(name: str) -> str:
    return f"Hello, {name}"

# Optional (use | None instead of Optional)
def find_user(id: int) -> User | None:
    ...

# Collections (use built-in types)
def process(items: list[str], mapping: dict[str, int]) -> set[int]:
    ...

# Union types
def handle(data: str | bytes | None) -> bool:
    ...

# Callable
from collections.abc import Callable
def apply(func: Callable[[int, int], int], a: int, b: int) -> int:
    return func(a, b)

# TypeVar for generics
from typing import TypeVar
T = TypeVar('T')
def first(items: list[T]) -> T | None:
    return items[0] if items else None
```

### Pydantic Models

```python
from pydantic import BaseModel, Field, field_validator

class UserCreate(BaseModel):
    email: str = Field(..., min_length=5)
    age: int = Field(..., ge=0, le=150)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()
```

**Review Checklist:**
- [ ] Public functions have type hints
- [ ] Return types specified
- [ ] Pydantic for data validation at boundaries
- [ ] Using modern union syntax (`X | Y` not `Union[X, Y]`)
- [ ] Generic types properly constrained

---

## Common Pitfalls

### Mutable Default Arguments

```python
# BAD - Mutable default is shared
def add_item(item, items=[]):
    items.append(item)
    return items

# GOOD - Use None as default
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### Late Binding Closures

```python
# BAD - All lambdas capture final value of i
funcs = [lambda: i for i in range(3)]
[f() for f in funcs]  # [2, 2, 2]

# GOOD - Capture value at creation time
funcs = [lambda i=i: i for i in range(3)]
[f() for f in funcs]  # [0, 1, 2]
```

### Exception Handling

```python
# BAD - Bare except
try:
    risky_operation()
except:
    pass

# BAD - Too broad
try:
    risky_operation()
except Exception:
    pass

# GOOD - Specific exceptions
try:
    risky_operation()
except (ValueError, TypeError) as e:
    logger.error(f"Operation failed: {e}")
    raise
```

### Resource Management

```python
# BAD - Manual resource management
f = open('file.txt')
data = f.read()
f.close()  # May not run if exception

# GOOD - Context manager
with open('file.txt') as f:
    data = f.read()

# GOOD - Custom context manager
from contextlib import contextmanager

@contextmanager
def managed_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)
```

**Review Checklist:**
- [ ] No mutable default arguments
- [ ] Context managers for resources
- [ ] Specific exception handling
- [ ] No bare `except:` clauses
- [ ] Proper use of `finally` for cleanup

---

## Async Python

### Async Best Practices

```python
# BAD - Blocking call in async function
async def fetch_data():
    response = requests.get(url)  # Blocks event loop!
    return response.json()

# GOOD - Use async HTTP client
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

```python
# BAD - Sequential when parallel is possible
async def get_all():
    a = await fetch_a()
    b = await fetch_b()
    return a, b

# GOOD - Parallel execution
async def get_all():
    a, b = await asyncio.gather(fetch_a(), fetch_b())
    return a, b
```

### Async Patterns

```python
# Semaphore for rate limiting
sem = asyncio.Semaphore(10)

async def limited_fetch(url):
    async with sem:
        return await fetch(url)

# Timeout handling
async def fetch_with_timeout(url):
    try:
        async with asyncio.timeout(5.0):
            return await fetch(url)
    except asyncio.TimeoutError:
        return None
```

**Review Checklist:**
- [ ] No blocking calls in async functions
- [ ] `asyncio.gather` for parallel operations
- [ ] Proper timeout handling
- [ ] Semaphores for rate limiting
- [ ] Async context managers used correctly

---

## Testing

### Pytest Patterns

```python
# Fixtures for setup
@pytest.fixture
def user():
    return User(name="test", email="test@example.com")

@pytest.fixture
def db_session():
    session = create_session()
    yield session
    session.rollback()
    session.close()

# Parametrized tests
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_uppercase(input, expected):
    assert uppercase(input) == expected

# Async tests
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

### Mocking

```python
from unittest.mock import Mock, patch, AsyncMock

# Patch external dependencies
@patch('mymodule.external_api')
def test_with_mock(mock_api):
    mock_api.return_value = {"data": "mocked"}
    result = my_function()
    mock_api.assert_called_once()

# Async mock
@patch('mymodule.async_fetch', new_callable=AsyncMock)
async def test_async_mock(mock_fetch):
    mock_fetch.return_value = {"data": "mocked"}
    result = await my_async_function()
```

**Review Checklist:**
- [ ] Tests are isolated (no shared state)
- [ ] Fixtures for common setup
- [ ] Parametrized tests for multiple cases
- [ ] External dependencies mocked
- [ ] Async code tested with pytest-asyncio
- [ ] Edge cases covered

---

## Package Structure

### Recommended Layout

```
mypackage/
├── pyproject.toml
├── src/
│   └── mypackage/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   └── models.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── conftest.py
│   ├── test_core/
│   └── test_api/
└── README.md
```

### pyproject.toml

```toml
[project]
name = "mypackage"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.100",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.1",
    "mypy>=1.0",
]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "UP"]

[tool.mypy]
strict = true
```

**Review Checklist:**
- [ ] src layout used
- [ ] pyproject.toml for configuration
- [ ] Dependencies properly specified
- [ ] Dev dependencies separated
- [ ] Linter and type checker configured

# CareerAI Coding Standards

**Project:** CareerAI  


---

# 1. Purpose

This document defines the coding standards and development practices followed throughout the CareerAI project.

The objective is to ensure that the codebase remains:

- Clean
- Readable
- Maintainable
- Scalable
- Consistent
- Production-ready

Every contributor is expected to follow these standards before committing code.

---

# 2. Core Engineering Principles

The following principles apply to every module in the project.

- Readability over cleverness.
- Keep code simple.
- Follow the Single Responsibility Principle (SRP).
- Avoid code duplication (DRY).
- Prefer composition over unnecessary inheritance.
- Never hardcode configuration values.
- Write code for maintainability, not just functionality.

---

# 3. Project Structure

```
career-ai/

app/
│
├── agents/
├── config/
├── database/
├── models/
├── repositories/
├── services/
├── utils/

scripts/
tests/
docs/

docker-compose.yml
requirements.txt
README.md
.env
```

Each directory should have a single responsibility.

---

# 4. Python Standards

## Python Version

Python 3.12+

## Style Guide

- Follow PEP 8.
- Maximum line length: 88 characters.
- Use 4 spaces for indentation.
- Do not use tabs.

---

# 5. Naming Conventions

## Variables

Use snake_case.

```python
user_name
job_title
resume_score
```

---

## Functions

Use verbs.

```python
get_jobs()
classify_resume()
predict_salary()
```

---

## Classes

Use PascalCase.

```python
JobScraper
ResumeParser
SkillExtractor
```

---

## Files

Use snake_case.

```
resume_parser.py
job_scraper.py
settings.py
```

---

## Constants

Use UPPER_CASE.

```python
MAX_RETRY_COUNT
DEFAULT_TIMEOUT
API_VERSION
```

---

# 6. Import Standards

Group imports in the following order:

1. Standard library
2. Third-party libraries
3. Local project imports

Example:

```python
import os
from pathlib import Path

from pydantic_settings import BaseSettings

from app.config.settings import settings
```

Never use:

```python
from module import *
```

---

# 7. Type Hints

All public functions must include type hints.

Correct:

```python
def classify_resume(text: str) -> dict:
```

Incorrect:

```python
def classify_resume(text):
```

---

# 8. Documentation

Every public module, class and function must contain a docstring.

Example:

```python
def get_jobs() -> list:
    """
    Retrieve jobs from configured job sources.

    Returns:
        list: List of job records.
    """
```

---

# 9. Function Design

Functions should:

- Perform one responsibility.
- Be short and readable.
- Return explicit values.
- Avoid unnecessary nesting.

Recommended maximum length:

30 lines

---

# 10. Class Design

Each class should represent one logical component.

Good:

```
JobScraper
ResumeAnalyzer
SkillExtractor
```

Avoid large "God Classes" responsible for multiple unrelated tasks.

---

# 11. Configuration

Never hardcode:

- API Keys
- Database credentials
- Passwords
- Secrets
- URLs

Always use:

```
.env

↓

settings.py

↓

Application
```

---

# 12. Logging

Use the logging module.

Correct:

```python
logger.info("Connected to PostgreSQL")
```

Avoid:

```python
print("Connected")
```

Exception:

Temporary debugging during development.

---

# 13. Error Handling

Never ignore exceptions.

Incorrect:

```python
except:
    pass
```

Correct:

```python
except Exception as error:
    logger.exception(error)
    raise
```

---

# 14. Database Standards

- Use SQLAlchemy ORM.
- Never write database credentials inside code.
- Use migrations for schema changes.
- Always use transactions where appropriate.
- Parameterize queries.

---

# 15. AI Agent Standards

Each AI Agent must have a single responsibility.

Example:

```
Job Scraper Agent

Resume Parser Agent

Skill Extraction Agent

Recommendation Agent
```

Agents should communicate through well-defined interfaces.

---

# 16. Git Workflow

Development workflow:

```
Develop

↓

Test

↓

Commit

↓

Push
```

Never commit untested code.

---

# 17. Commit Message Convention

Use Conventional Commits.

Examples:

```
feat: add resume parser

fix: resolve redis connection

refactor: simplify database layer

docs: update coding standards

test: add configuration tests

chore: update dependencies
```

---

# 18. Testing

Every completed module should be tested before commit.

Testing includes:

- Functional testing
- Error handling
- Configuration validation
- Database connectivity (if applicable)

---

# 19. Code Review Checklist

Before pushing code, verify:

- Code follows PEP 8.
- No hardcoded secrets.
- Type hints added.
- Imports organized.
- Functions have single responsibility.
- Logging added where necessary.
- Tests completed.
- Documentation updated.

---

# 20. Definition of Done

A feature is considered complete only if:

- Functionality implemented.
- Code tested.
- Coding standards followed.
- Documentation updated.
- Git commit created.
- Successfully pushed to GitHub.

---

# 21. References

- PEP 8 – Python Style Guide
- PEP 257 – Docstring Conventions
- SQLAlchemy Documentation
- Pydantic Documentation
- Docker Documentation

---


---
name: Architecture
description: Rules for the conceptual architecture and data flow.
---

- React → REST → FastAPI → Business/Smart Logic → MySQL
- separation of concerns
- modular architecture
- frontend never accesses MySQL directly
- API contract between frontend/backend
- business logic separated from route handlers
- avoid unnecessary abstraction
- maintainable structure
- explain architectural decisions for viva

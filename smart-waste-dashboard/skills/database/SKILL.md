---
name: Database
description: Rules for MySQL database schema and access.
---

Use the recommended relational model:
locations
waste_records
collection_records
users (only if authentication is attempted)

Rules:

- MySQL is the required/default database
- foreign keys
- primary keys
- sensible constraints
- parameterized queries
- avoid unnecessary tables
- seed data should be realistic
- preserve referential integrity
- do not put secrets in SQL files

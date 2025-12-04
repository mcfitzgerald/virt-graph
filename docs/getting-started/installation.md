# Installation

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Poetry (Python package manager)

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/mcfitzgerald/virt-graph.git
cd virt-graph
```

### 2. Install Dependencies

```bash
poetry install
```

### 3. Start PostgreSQL

```bash
docker-compose -f postgres/docker-compose.yml up -d
```

This starts a PostgreSQL 14 container with:

- Database: `supply_chain`
- User: `virt_graph`
- Password: `dev_password`
- Port: `5432`

The schema and seed data are automatically loaded on first start.

### 4. Verify Installation

```bash
# Run tests
poetry run pytest

# Check database connection
docker-compose -f postgres/docker-compose.yml ps
```

## Development Dependencies

Install development tools:

```bash
poetry install --with dev
```

This adds:

- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `mkdocs` - Documentation
- `mkdocs-material` - Documentation theme

## Database Management

```bash
# Start database
docker-compose -f postgres/docker-compose.yml up -d

# View logs
docker-compose -f postgres/docker-compose.yml logs -f

# Stop database
docker-compose -f postgres/docker-compose.yml down

# Reset database (delete data)
docker-compose -f postgres/docker-compose.yml down -v
docker-compose -f postgres/docker-compose.yml up -d
```

## Regenerating Seed Data

If you need to regenerate the synthetic data:

```bash
poetry run python scripts/generate_data.py
```

Then restart PostgreSQL to reload:

```bash
docker-compose -f postgres/docker-compose.yml down -v
docker-compose -f postgres/docker-compose.yml up -d
```

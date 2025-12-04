# Installation

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Poetry (Python package manager)

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/virt-graph.git
cd virt-graph
```

### 2. Install Dependencies

```bash
poetry install
```

### 3. Start PostgreSQL

```bash
docker-compose up -d
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
docker-compose ps
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
docker-compose up -d

# View logs
docker-compose logs -f postgres

# Stop database
docker-compose down

# Reset database (delete data)
docker-compose down -v
docker-compose up -d
```

## Regenerating Seed Data

If you need to regenerate the synthetic data:

```bash
poetry run python scripts/generate_data.py
```

Then restart PostgreSQL to reload:

```bash
docker-compose down -v
docker-compose up -d
```

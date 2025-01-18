## Getting Started

Create a python virtual env:
```
python3 -m venv .venv-iw
source ~/.venv-iw/bin/activate
```

Install infinite-website as a local python package, with all dependencies:
```
pip install -e .
```

Ensure you have `IW_DB_URL` and `ANTHROPIC_API_KEY` env vars set. Then, run the server:
```
python src/server.py
```

The website should now be live at `localhost:8008`

## Setting Up Local DB

Install and start postgres 16, then create infinite-website DB:
```
brew install postgresql@16
brew services start postgresql@16
createdb infinite-website

# probably also add the following to your ~/.bashrc
export IW_DB_URL='postgresql://localhost:5432/infinite-website'
```

Run alembic migrations (`IW_DB_URL` env var must be set):
```
cd /path/to/infinite-website/src/db
alembic migrate head
```

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

Ensure you have `IW_DB_URL`, `ANTHROPIC_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY_ID`, and `AWS_S3_BUCKET` env vars set. Then, run the server:
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

## Setting up AWS S3

To allow for image uploads, you must create an AWS S3 bucket with public read access, and an IAM account with write access permissions `s3:PutObject`, `s3:ListBucket`, and `s3:GetBucketLocation` on resources `arn:aws:s3:::your-bucket-name` and `arn:aws:s3:::your-bucket-name/*`.

Then, set the env var `AWS_S3_BUCKET` to the bucket name, and env vars `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY_ID` to the IAM account credentials.

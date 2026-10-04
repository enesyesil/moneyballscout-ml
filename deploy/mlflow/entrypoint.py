"""Create the MLflow database and artifact bucket if missing, then start the tracking server."""
import os
import time

import boto3
import psycopg2
from botocore.exceptions import ClientError

pg = dict(host=os.environ["PGHOST"], user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"], dbname="postgres")
for attempt in range(30):
    try:
        conn = psycopg2.connect(**pg)
        break
    except psycopg2.OperationalError:
        time.sleep(2)
else:
    raise SystemExit("postgres not reachable")
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'mlflow'")
    if cur.fetchone() is None:
        cur.execute("CREATE DATABASE mlflow")
conn.close()

s3 = boto3.client("s3", endpoint_url=os.environ["MLFLOW_S3_ENDPOINT_URL"])
bucket = os.environ.get("S3_BUCKET", "scout")
try:
    s3.head_bucket(Bucket=bucket)
except ClientError:
    s3.create_bucket(Bucket=bucket)

os.execvp("mlflow", [
    "mlflow", "server", "--host", "0.0.0.0", "--port", "5000",
    "--backend-store-uri", f"postgresql://{pg['user']}:{pg['password']}@{pg['host']}:5432/mlflow",
    "--artifacts-destination", f"s3://{bucket}/mlflow", "--serve-artifacts",
])

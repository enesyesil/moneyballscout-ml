FROM ghcr.io/mlflow/mlflow:v2.18.0
RUN pip install --no-cache-dir psycopg2-binary boto3
COPY entrypoint.py /entrypoint.py
EXPOSE 5000
CMD ["python", "/entrypoint.py"]

FROM langflowai/langflow:latest

WORKDIR /app

COPY components ./components
COPY tests ./tests

RUN pip install --no-cache-dir aioboto3 pytest requests python-dotenv boto3

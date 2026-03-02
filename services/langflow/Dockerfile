FROM langflowai/langflow:1.7.2

WORKDIR /app

COPY components ./components
COPY tests ./tests

RUN pip install --no-cache-dir aioboto3 pytest pytest-asyncio requests python-dotenv boto3

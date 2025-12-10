FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# Install build dependencies for psycopg2
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8080"]

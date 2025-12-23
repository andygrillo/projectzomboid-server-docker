FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI and Compose plugin (to control host containers)
RUN apt-get update && apt-get install -y \
    docker.io \
    docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]

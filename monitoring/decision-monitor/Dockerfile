FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY reference ./reference
COPY sql ./sql
EXPOSE 9108
CMD ["python", "-m", "app.exporter"]

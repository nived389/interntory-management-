FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Kolkata HTTPS=1 INVENTORY_DATA=/var/lib/travelicious PORT=10000
WORKDIR /app
COPY requirements.txt requirements-production.txt requirements-turso.txt ./
RUN pip install --no-cache-dir -r requirements-turso.txt
COPY . .
EXPOSE 10000
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 1 --timeout 180 production:app"]

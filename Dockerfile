FROM python:3.11-slim

WORKDIR /app

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/health', timeout=3)" || exit 1

CMD gunicorn wsgi:app --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120

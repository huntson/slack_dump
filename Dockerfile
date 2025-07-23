FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install requirements
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy source
COPY app/ /app/

CMD ["python", "-u", "/app/main.py"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # If a dependency pulls in torch (e.g. BERTopic), get the small CPU-only build instead of the CUDA one.
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

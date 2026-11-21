FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Real model: uncomment, and mount/copy the weights to /app/models/model_inference.pt
# COPY requirements-ml.txt .
# RUN pip install --no-cache-dir -r requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
COPY scripts ./scripts

COPY app ./app
COPY samples ./samples

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

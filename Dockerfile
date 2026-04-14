FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Runner principal del proyecto (compat. RF14c-07..12)
ENTRYPOINT ["python", "-m", "src.erp_fraud.cli.main"]
CMD ["run", "--input-zip", "erp_fraud_data.zip"]

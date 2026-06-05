# Despliegue FastAPI en EC2 para defensa

## Objetivo

Arrancar la API FastAPI existente en la misma EC2 que Streamlit, escuchando solo en `127.0.0.1:8000`. Streamlit queda publica en `0.0.0.0:8501` y consume la API con:

```bash
ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

No se debe abrir el puerto `8000` al exterior.

## Entrypoint real

El objeto ASGI real esta en:

```bash
app.api.main:app
```

El fichero correspondiente es `app/api/main.py`. Define `create_app()` y crea `app = create_app()`.

Comando base:

```bash
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

## Dependencias

La API usa las dependencias del proyecto en `requirements.txt`, especialmente:

- `fastapi`
- `uvicorn`
- `python-multipart`
- `boto3`
- `duckdb`, `pandas`, `pyarrow`, `openpyxl` para servicios auxiliares como drilldown/cache
- `PyYAML`

Instalacion:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Variables de entorno

Crear el fichero local:

```bash
cp .env.api.ec2.example .env.api.ec2
nano .env.api.ec2
```

Configuracion normal:

```bash
ERP_FRAUD_API_HOST=127.0.0.1
ERP_FRAUD_API_PORT=8000
AWS_REGION=eu-west-1
S3_INPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/inputs/
S3_OUTPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/runs/
API_ECS_CLUSTER=tfg-fraud-dev-ecs-cluster
API_ECS_TASK_DEFINITION=tfg-fraud-dev-task
API_ECS_SUBNETS=subnet-...,subnet-...,subnet-...
API_ECS_SECURITY_GROUPS=sg-...
```

Secretos:

- No guardar secretos reales en `.env.api.ec2`.
- La API no necesita `OPENAI_API_KEY` ni `LANGSMITH_API_KEY` para arrancar ni para servir la UI.
- Los runs reales se ejecutan en ECS Fargate; los secretos de OpenAI/LangSmith deben seguir en la task definition/Secrets Manager.
- Para permisos AWS, preferir un IAM Role asociado a la EC2. Si se usa AWS CLI profile local, configurar `AWS_PROFILE`, pero no guardar claves en el repo.

## Dependencia AWS

La API en EC2 puede arrancar y responder `/health` por si misma. Para funcionalidad completa sigue dependiendo de AWS:

- Upload/listado de datasets: S3.
- Lanzamiento de runs reales: ECS Fargate.
- Consulta de estado de runs: ECS y S3.
- Resultados/reportes/drilldown: S3 y artefactos de runs.

Por tanto, la EC2 no ejecuta el pipeline completo localmente mediante la API actual. La API existente actua como capa HTTP que orquesta S3/ECS y lee artefactos.

## Arranque manual

Desde la raiz del repo:

```bash
chmod +x scripts/run_api_prod.sh
./scripts/run_api_prod.sh
```

Comprobacion local:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

## Arranque persistente con systemd

Instalar servicio:

```bash
chmod +x scripts/deploy_api_ec2.sh
./scripts/deploy_api_ec2.sh
sudo systemctl start erp-fraud-api.service
```

Comprobar estado:

```bash
sudo systemctl status erp-fraud-api.service
```

Logs:

```bash
sudo journalctl -u erp-fraud-api.service -f
```

Reiniciar:

```bash
sudo systemctl restart erp-fraud-api.service
```

Si el usuario de la instancia no es `ubuntu`:

```bash
RUN_USER=ec2-user ./scripts/deploy_api_ec2.sh
```

## Conectar Streamlit con la API local

En `.env.streamlit.ec2`:

```bash
ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_PORT=8501
```

Arrancar ambos servicios:

```bash
sudo systemctl start erp-fraud-api.service
sudo systemctl start erp-fraud-streamlit.service
```

Comprobar:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8501
```

## Puertos en Security Group

Abrir solo:

- TCP `8501` para Streamlit.
- SSH `22` solo desde tu IP si necesitas administracion.

No abrir TCP `8000`. FastAPI debe quedar limitada a localhost.

## Troubleshooting minimo

API no arranca:

```bash
sudo systemctl status erp-fraud-api.service
sudo journalctl -u erp-fraud-api.service -n 100
```

`/health` funciona pero no lista datasets/runs:

- Revisar `S3_INPUT_URI` y `S3_OUTPUT_URI`.
- Revisar permisos IAM de la instancia.
- Revisar `AWS_REGION`.

Crear run falla:

- Revisar `API_ECS_CLUSTER`.
- Revisar `API_ECS_TASK_DEFINITION`.
- Revisar `API_ECS_SUBNETS` y `API_ECS_SECURITY_GROUPS`.
- Revisar permisos `ecs:RunTask` e `iam:PassRole`.

Streamlit no conecta con API:

- Revisar `.env.streamlit.ec2`.
- Confirmar `ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1`.
- Reiniciar Streamlit tras cambiar el fichero:

```bash
sudo systemctl restart erp-fraud-streamlit.service
```

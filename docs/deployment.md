# Despliegue

El proyecto tiene dos vías de despliegue distintas y complementarias.

## 1. EC2 pública para defensa

Objetivo: permitir que un revisor abra la interfaz en navegador.

Arquitectura:

- Streamlit público en `0.0.0.0:8501`.
- FastAPI solo local en `127.0.0.1:8000`.
- Streamlit consume `ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1`.
- Solo se abre el puerto `8501` en el Security Group.

URL de demo actual:

```text
http://100.57.8.239:8501
```

Servicios systemd:

- `deploy/erp-fraud-api.service`
- `deploy/erp-fraud-streamlit.service`

Scripts:

- `scripts/run_api_prod.sh`
- `scripts/run_streamlit_prod.sh`
- `scripts/deploy_api_ec2.sh`
- `scripts/deploy_streamlit_ec2.sh`

Documentación detallada:

- `docs/deploy_api_ec2.md`
- `docs/deploy_streamlit_ec2.md`

### Comandos mínimos en EC2

```bash
./scripts/deploy_api_ec2.sh
./scripts/deploy_streamlit_ec2.sh

sudo systemctl start erp-fraud-api.service
sudo systemctl start erp-fraud-streamlit.service
```

Comprobaciones:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8501
```

## 2. AWS batch con ECS/Fargate

Objetivo: ejecutar el pipeline como job desacoplado.

Servicios documentados:

- S3: inputs, outputs y state.
- ECR: imagen Docker.
- ECS Fargate: ejecución del pipeline.
- CloudWatch Logs: logs de contenedor.
- Secrets Manager: secretos OpenAI/LangSmith.
- IAM: roles de task y ejecución.
- EventBridge/Lambda: automatización por schedule o cambios de artefactos.

Documentación consolidada:

- `docs/cloud/cloud_aws.md`
- `docs/cloud/rf14c_final_verification.md`

Código/infra relacionada:

- `Dockerfile`
- `.github/workflows/ecr-publish-main.yml`
- `lambda/rf14c23/lambda_function.py`
- `scripts/build_and_push_ecr.sh`

## Diferencia clave

La EC2 pública no sustituye el backend batch. En la vía de defensa, la UI y la API viven en la misma EC2, pero los runs reales se lanzan contra ECS/Fargate y leen/escriben artefactos en S3.

## Variables normales y secretos

### EC2 API

Plantilla:

- `.env.api.ec2.example`

Variables normales:

- `ERP_FRAUD_API_HOST`
- `ERP_FRAUD_API_PORT`
- `AWS_REGION`
- `S3_INPUT_URI`
- `S3_OUTPUT_URI`
- `API_ECS_CLUSTER`
- `API_ECS_TASK_DEFINITION`
- `API_ECS_SUBNETS`
- `API_ECS_SECURITY_GROUPS`

Secretos:

- No deben guardarse en `.env.api.ec2`.
- Para runs reales, OpenAI/LangSmith deben seguir en Secrets Manager o en el entorno seguro del backend.

### EC2 Streamlit

Plantilla:

- `.env.streamlit.ec2.example`

Variables normales:

- `ERP_FRAUD_API_BASE_URL`
- `STREAMLIT_SERVER_ADDRESS`
- `STREAMLIT_SERVER_PORT`

La UI no necesita claves AWS, OpenAI ni LangSmith.

## Puertos

| Puerto | Exposición | Uso |
|---|---|---|
| `8501` | Público | Streamlit |
| `8000` | Solo localhost | FastAPI |
| `22` | Restringido | Administración SSH |

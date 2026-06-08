# Despliegue Streamlit en EC2 publica

## Objetivo

Publicar la interfaz Streamlit del proyecto en una instancia EC2 publica para que el tribunal pueda abrirla desde un navegador. Esta via no sustituye la arquitectura cloud existente de backend/batch; solo despliega la capa de interfaz.

## URL publica de defensa

La instancia documentada para revisión externa expone Streamlit en:

```text
http://100.57.8.239:8501
```

Esta URL depende de que la instancia EC2 y los servicios systemd estén activos. Si la IP cambia, actualizar también `README.md` y `docs/deployment.md`.

## Entrada de Streamlit

El archivo de entrada es:

```bash
app/ui/Home.py
```

El comando base es:

```bash
python -m streamlit run app/ui/Home.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
```

## Como se conecta la UI

La UI no ejecuta directamente el analisis antifraude. Usa `app/ui/services/api_client.py` y llama a una API HTTP configurada por:

```bash
ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Si esa variable no existe, el codigo usa por defecto `http://localhost:8000/api/v1`.

Para una demo completa con datasets, runs, resultados y drilldown, debe existir una API FastAPI accesible desde la EC2. La via recomendada para defensa es arrancar esa API en la misma instancia, escuchando solo en `127.0.0.1:8000`, y configurar Streamlit con `ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1`. Esa API sigue siendo la que accede a S3/ECS/Fargate/CloudWatch segun la arquitectura ya implementada.

## Prerequisitos de EC2

Instancia recomendada para defensa:

- Ubuntu 22.04 o 24.04.
- Security Group con TCP `8501` abierto desde la IP del tribunal o temporalmente desde `0.0.0.0/0`.
- Python 3 y venv.
- Git si se va a clonar el repositorio desde GitHub.

Instalacion base:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## Instalacion del proyecto

Ruta recomendada para que el service file funcione sin cambios:

```bash
sudo mkdir -p /opt/erp-fraud-data-TFG
sudo chown ubuntu:ubuntu /opt/erp-fraud-data-TFG
cd /opt/erp-fraud-data-TFG
git clone https://github.com/luciasorni/erp-fraud-data-TFG.git .
```

Si se usa un fork o repositorio privado de entrega, sustituir la URL anterior por la URL correspondiente.

Instalar dependencias:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Variables de entorno

Crear el fichero local de entorno:

```bash
cp .env.streamlit.ec2.example .env.streamlit.ec2
nano .env.streamlit.ec2
```

Variables normales:

```bash
ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_PORT=8501
```

Secretos:

- La UI Streamlit no necesita `OPENAI_API_KEY`.
- La UI Streamlit no necesita `LANGSMITH_API_KEY`.
- La UI Streamlit no necesita claves AWS directamente.
- Si en la misma EC2 tambien se arranca la API FastAPI, entonces los secretos y permisos AWS pertenecen a la API/backend, no a Streamlit.

No guardar secretos reales en el repositorio.

## Arranque manual

Desde la raiz del repo:

```bash
chmod +x scripts/run_streamlit_prod.sh
./scripts/run_streamlit_prod.sh
```

URL esperada:

```text
http://100.57.8.239:8501
```

En la instancia de defensa actual:

```text
http://100.57.8.239:8501
```

## Arranque persistente con systemd

El instalador usa por defecto la ruta real del repo desde la que se ejecuta. La ruta recomendada es `/opt/erp-fraud-data-TFG` y el usuario por defecto es `ubuntu`.

Instalacion automatica:

```bash
cd /opt/erp-fraud-data-TFG
chmod +x scripts/deploy_streamlit_ec2.sh
./scripts/deploy_streamlit_ec2.sh
sudo systemctl start erp-fraud-streamlit.service
```

Comprobar estado:

```bash
sudo systemctl status erp-fraud-streamlit.service
```

Ver logs:

```bash
sudo journalctl -u erp-fraud-streamlit.service -f
```

Reiniciar:

```bash
sudo systemctl restart erp-fraud-streamlit.service
```

Si quieres forzar otra ruta o el usuario no es `ubuntu`, ejecutar:

```bash
PROJECT_DIR=/ruta/al/repo RUN_USER=<usuario> ./scripts/deploy_streamlit_ec2.sh
```

## Puerto a abrir

Abrir TCP `8501` en el Security Group de la instancia.

No hace falta Nginx para la defensa si se acepta acceder con:

```text
http://100.57.8.239:8501
```

Nginx solo seria necesario si se quiere usar dominio, HTTPS o puerto 80/443.

## Modalidades de despliegue

### UI sola

Arranca Streamlit y muestra la interfaz. Las secciones que consultan datasets, runs, resultados o drilldown necesitan que `ERP_FRAUD_API_BASE_URL` apunte a una API disponible. Si la API no responde, la UI muestra errores controlados de conexion.

### UI + API existente

Opcion recomendada para defensa si ya hay backend operativo. Streamlit vive en EC2 y `ERP_FRAUD_API_BASE_URL` apunta a la API FastAPI desplegada o arrancada aparte.

### UI + API en la misma EC2

Es la opcion recomendada para defensa. Apunta a `http://127.0.0.1:8000/api/v1`, despliega la API con `docs/deploy_api_ec2.md` y da permisos/configuracion AWS a la instancia para S3/ECS/Fargate. El puerto `8000` no debe abrirse al exterior.

## Troubleshooting minimo

La pagina no carga:

```bash
sudo systemctl status erp-fraud-streamlit.service
sudo journalctl -u erp-fraud-streamlit.service -n 100
```

El navegador no conecta:

- Confirmar que el Security Group permite TCP `8501`.
- Confirmar que Streamlit escucha en `0.0.0.0`.
- Probar en la instancia: `curl http://127.0.0.1:8501`.

La UI carga pero no lista runs o datasets:

- Revisar `ERP_FRAUD_API_BASE_URL` en `.env.streamlit.ec2`.
- Probar health de la API:

```bash
curl "$ERP_FRAUD_API_BASE_URL/health"
```

Error de dependencias:

```bash
. .venv/bin/activate
python -m pip install -r requirements.txt
```

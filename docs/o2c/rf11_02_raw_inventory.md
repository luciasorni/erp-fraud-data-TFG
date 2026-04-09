# RF11-02 — Inventario `raw_data` para O2C y Correspondencia Preliminar

Fecha: 2026-04-09  
Estado: Cerrado

## 1) Objetivo

Inventariar tablas disponibles en `erp_fraud_data/raw_data` relevantes para O2C y dejar una correspondencia preliminar hacia entidades canónicas O2C.

## 2) Evidencia generada

Archivo máquina:

- `docs/o2c/artifacts/rf11_02_raw_inventory.json`

Comando reproducible usado para regenerar evidencia:

```bash
python3 - <<'PY'
from pathlib import Path
import zipfile, json

zip_path = Path("erp_fraud_data.zip")
raw_prefix = "erp_fraud_data/raw_data/"

with zipfile.ZipFile(zip_path) as z:
    nested = sorted(
        n for n in z.namelist()
        if n.startswith(raw_prefix) and n.lower().endswith(".zip")
    )

summary = {"raw_nested_archives": nested, "datasets": {}}

def stem(name: str) -> str:
    base = name.split("/")[-1]
    if "." not in base:
        return ""
    return base.rsplit(".", 1)[0].upper()

from io import BytesIO
with zipfile.ZipFile(zip_path) as outer:
    for nested_name in nested:
        dataset = Path(nested_name).name
        with zipfile.ZipFile(BytesIO(outer.read(nested_name))) as inner:
            members = [m for m in inner.namelist() if not m.endswith("/")]
        stems = sorted({stem(m) for m in members if stem(m)})
        summary["datasets"][dataset] = {"files": sorted(members), "table_stems": stems}

coverage = {}
for ds, data in summary["datasets"].items():
    for t in data["table_stems"]:
        coverage.setdefault(t, []).append(ds)

summary["table_coverage"] = {k: sorted(v) for k, v in sorted(coverage.items())}

out = Path("docs/o2c/artifacts/rf11_02_raw_inventory.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(out)
PY
```

## 3) Resultado del inventario

- Datasets internos detectados en `raw_data`: `5` (`fraud_1.zip`, `fraud_2.zip`, `fraud_3.zip`, `normal_1.zip`, `normal_2.zip`).
- Tablas únicas detectadas por nombre de fichero: `90`.
- Cobertura O2C relevante:
  - `VBAK`, `VBAP`, `VBPA`, `LIPS`, `KNA1`: presentes en los 5 datasets.
  - `LIKP`, `BKPF`, `BSEG`: presentes en 4 datasets.
  - `KNB1`, `KONV`: presentes en 3 datasets.
  - `VBRK`, `VBRP`, `BSID`, `BSAD`: no detectadas por nombre de tabla.

## 4) Correspondencia preliminar raw -> canónico O2C

1. `o2c_order`
- Tablas candidatas: `VBAK` (cabecera), `VBAP` (posiciones), `VBPA` (partners), `KONV` (condiciones si disponible).

2. `o2c_delivery`
- Tablas candidatas: `LIKP` (cabecera entrega, cuando exista), `LIPS` (posiciones entrega).

3. `o2c_invoice`
- Sin `VBRK/VBRP` en este dataset por nombre de fichero.
- Estrategia preliminar: reconstrucción parcial de facturación vía `BKPF/BSEG` + vínculos operativos (`VBAP/LIPS`) cuando se puedan establecer.

4. `o2c_collection`
- Sin `BSID/BSAD` detectadas.
- Estrategia preliminar: aproximación desde partidas contables (`BSEG`) y metadatos contables (`BKPF`) hasta validar campos de compensación/cobro.

5. `o2c_customer`
- Tablas candidatas: `KNA1` (maestro cliente), `KNB1` (datos de sociedad si existe).

## 5) Riesgos abiertos de RF11-02

1. Falta de tablas SD clásicas de billing (`VBRK/VBRP`) obliga a inferencia contable de invoice/collection.
2. Cobertura heterogénea por dataset (tablas presentes en 3/4 de 5) exige validaciones por disponibilidad antes de transformar.
3. El inventario actual es por nombre de tabla; la validación de columnas obligatorias queda para RF11-03 y RF11-05.

## 6) Decisión para siguiente tarea

RF11-03 se implementará sobre este principio:

- Definir `canonical_schema_o2c.yaml` con campos `required` vs `optional` por entidad.
- Marcar explícitamente qué campos dependen de tablas no siempre presentes.
- Diseñar el modelo para degradación controlada (no abortar todo O2C si falta una tabla no crítica).

## 7) Criterios de aceptación de RF11-02

Se consideran cumplidos:

1. Existe inventario reproducible de `raw_data`.
2. Hay correspondencia preliminar raw -> entidades canónicas O2C.
3. Quedan documentados gaps de datos y su impacto técnico inmediato.

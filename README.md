# Demo: AirSupply → Navision (Sales Order)

Flujo: CSV AirSupply → mapeo referencias → Excel/CSV Navision (orden de venta).

## Uso rápido
1) Crear venv e instalar deps:
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt

2) Colocar el CSV real en `data/input/` (ej.: PO_AirSupply_*.csv)

3) Ajustar `config/config.yaml` (cliente, contrato, tipo, almacén).

4) Ejecutar:
   python -m src.app.main --in data/input/PO_AirSupply.csv --map data/mappings/referencias_cruzadas_fake.csv --out data/output/OrdenVenta_Simulada.xlsx

## Estructura
- src/core: lógica de negocio (transform, mapping)
- src/io: lectura/escritura (CSV, Excel)
- src/app: punto de entrada CLI
- config: parámetros fijos
- data/input: CSV AirSupply
- data/mappings: referencias SAP→Navision
- data/output: resultados

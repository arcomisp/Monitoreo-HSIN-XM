# Monitoreo HSIN · XM

Análisis diario automatizado de la hidrología del Sistema Interconectado Nacional (SIN) de Colombia: aportes hídricos por región, reservas de los embalses frente a la Senda de Referencia (Res. CREG 209 de 2020) y la Curva de Administración del Riesgo (CAR), y vertimientos.

Autor: **Alejandro Aroca**, Ingeniero Eléctrico · Consultor y Auditor Senior en Proyectos de Energía.

## Qué hace

Todos los días a las 7:40 a.m. (hora de Colombia), GitHub Actions ejecuta el flujo `.github/workflows/diario.yml`:

1. Consulta la API pública de XM (`servapibi.xm.com.co`).
2. Calcula los indicadores (`src/xm_brief.py`) y guarda el resultado en `reportes/json/AAAA-MM-DD.json`.
3. Genera el brief con alertas (`src/brief_md.py`) en `reportes/AAAA-MM-DD.md` y `reportes/ULTIMO.md`.
4. Actualiza los datos del tablero `dashboard/index.html` (`src/update_dashboard.py`).
5. Guarda los cambios con un commit "Datos XM al AAAA-MM-DD".

También se puede ejecutar a mano: pestaña **Actions → Análisis diario XM → Run workflow**.

## Criterios metodológicos

- **Aportes (flujo):** promedio acumulado del mes, del día 1 a la fecha de corte, frente a la media histórica de XM del mismo período (GWh/día). Nunca se promedian porcentajes diarios.
- **Reservas (stock):** % de capacidad útil al corte. La variación se reporta en puntos porcentuales y en GWh, porque los cambios de capacidad útil (p. ej. Ituango, 5-oct-2026) mueven el % sin cambiar el agua almacenada.
- **Regiones:** Antioquia, Caldas, Caribe, Centro, Oriente y Valle, según la región hidrológica que XM asigna a cada río. Caldas incluye las desviaciones Guarino y Manso; se reporta también el % sin desviaciones.
- **Aportes Naturales / HSIN:** se excluyen las desviaciones EEPPM, Batatas y Chivor.
- **Senda de Referencia:** Invierno 2026 (publicada por XM el 27-abr-2026), con horizonte hasta el 30-nov-2026. Al publicarse la nueva senda hay que actualizar `SENDA` en `src/xm_brief.py` y los escenarios `ESC` en `src/update_dashboard.py`.

## Alertas

| Alerta | Umbral |
|---|---|
| Región con aportes bajos | < 60 % de la media |
| Aportes del SIN bajos | < 80 % de la media |
| Reservas bajo la senda | brecha < −2 pp |
| Caída de reservas | > 1 pp en 7 días |
| Vertimientos con embalse bajo | > 1 GWh en el mes con reservas < 80 % |
| Cercanía a la CAR | margen < 10 pp |

## Uso local

Solo requiere Python 3.10 o superior, sin librerías adicionales.

```bash
python3 src/xm_brief.py > xm.json             # último día disponible
python3 src/xm_brief.py 2026-08-18 > xm.json  # fecha de corte específica
python3 src/brief_md.py xm.json
python3 src/update_dashboard.py dashboard/index.html dashboard/index.html
```

## Fuente

XM S.A. E.S.P., API pública de datos (Sinergox). Las cifras están sujetas a las revisiones que XM publica en los días siguientes a cada corte.

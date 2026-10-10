#!/usr/bin/env python3
"""Guarda una copia del tablero del día en historico/AAAA-MM-DD/ y regenera el índice historico/index.html.
Uso: python3 src/archivar.py AAAA-MM-DD   (fecha de corte de los datos de XM)"""
import datetime as dt, html, json, os, re, shutil, sys

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def fecha_larga(s):
    d = dt.date.fromisoformat(s)
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(s):
    d = dt.date.fromisoformat(s)
    return f"{DIAS[d.weekday()][:3]} {d.day} {MESES[d.month - 1][:3]} {d.year}"


def n(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def archivar(fecha):
    dst = os.path.join("historico", fecha)
    os.makedirs(os.path.join(dst, "reportes"), exist_ok=True)
    for f in ("DIAGNOSTICO.html", "ULTIMO.html"):
        if os.path.exists(os.path.join("reportes", f)):
            shutil.copy(os.path.join("reportes", f), os.path.join(dst, "reportes", f))
    s = open("index.html", encoding="utf-8").read()
    s = s.replace('href="peticiones/', 'href="../../peticiones/').replace('href="historico/', 'href="../')
    aviso = (f'<div class="hist-aviso" role="note"><b>Histórico:</b> está viendo IA HSIN Colombia con el corte del '
             f'{html.escape(fecha_larga(fecha))}. <a href="../../">Ver la versión actual</a> · <a href="../">Otras fechas</a></div>\n')
    estilo = ('<style>.hist-aviso{position:sticky;top:0;z-index:50;background:#eda100;color:#0f1a22;padding:10px 16px;'
              'font:600 14px/1.4 "IBM Plex Sans",system-ui,sans-serif;text-align:center}.hist-aviso a{color:#0f1a22}</style>\n')
    k = s.index("<header")
    s = s[:k] + estilo + aviso + s[k:]
    open(os.path.join(dst, "index.html"), "w", encoding="utf-8").write(s)


def resumen(fecha):
    """Reserva, aportes del mes y nivel de riesgo de un corte, para el índice."""
    r = {}
    try:
        j = json.load(open(os.path.join("reportes", "json", f"{fecha}.json"), encoding="utf-8"))
        r["res"] = j["reservas"]["pct"]
        r["ap"] = j["aportes_mes"]["SIN"]["pct"]
    except Exception:
        pass
    try:
        t = open(os.path.join("historico", fecha, "reportes", "DIAGNOSTICO.html"), encoding="utf-8").read()
        m = re.search(r"Riesgo (BAJO|MODERADO|ALTO)", t)
        if m:
            r["nivel"] = m.group(1)
    except Exception:
        pass
    return r


def indice():
    fechas = sorted((d for d in os.listdir("historico") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)), reverse=True)
    filas = []
    for f in fechas:
        r = resumen(f)
        nivel = r.get("nivel", "")
        chip = f'<span class="niv niv-{nivel.lower()}">{nivel.capitalize()}</span>' if nivel else "–"
        filas.append(
            f'<tr><td><a href="{f}/">{fecha_corta(f)}</a></td>'
            f'<td class="n">{n(r["res"]) + " %" if "res" in r else "–"}</td>'
            f'<td class="n">{n(r["ap"], 0) + " %" if "ap" in r else "–"}</td>'
            f'<td>{chip}</td></tr>')
    page = f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Histórico · IA HSIN Colombia</title>
<meta name="description" content="Consulta los informes diarios anteriores de IA HSIN Colombia: embalses, aportes y conclusión del día con datos oficiales de XM.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,500..800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#f6f8f9;--surface:#fff;--ink:#0f1a22;--ink-2:#4a5862;--ink-3:#7a8790;--rule:#dde4e8;--water:#2a78d6;
--f-display:"Archivo","Arial Narrow",system-ui,sans-serif;--f-body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1418;--surface:#161d22;--ink:#eef3f6;--ink-2:#b4c0c8;--ink-3:#8a979f;--rule:#2a343b;--water:#3987e5;color-scheme:dark}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--f-body)}}
main{{max-width:760px;margin:0 auto;padding:28px 16px 60px}}a{{color:var(--water)}}
h1{{font-family:var(--f-display);font-stretch:85%;font-size:clamp(26px,5vw,34px);line-height:1.1;margin:12px 0 6px}}
p{{color:var(--ink-2)}}
.tw{{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:12px}}
table{{border-collapse:collapse;width:100%;font-size:14.5px}}th,td{{padding:9px 10px;border-bottom:1px solid var(--rule);text-align:left;white-space:nowrap}}
th{{font-weight:600;color:var(--ink-2);font-size:13px}}td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}tr:last-child td{{border-bottom:0}}
.niv{{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12.5px;font-weight:600}}
.niv-bajo{{background:#1baf7a2e}}.niv-moderado{{background:#eda10033}}.niv-alto{{background:#e3494833}}
.foot{{margin-top:22px;font-size:13px;color:var(--ink-3)}}
</style></head><body><main>
<a href="../">← Volver a la versión actual</a>
<h1>Histórico de IA HSIN Colombia</h1>
<p>Cada día, después de la actualización automática de las 7:40 a. m., se guarda una copia completa del informe. Elija una fecha de corte para ver el informe tal como se publicó ese día.</p>
<div class="tw"><table>
<thead><tr><th>Corte</th><th class="n">Reserva</th><th class="n">Aportes</th><th>Riesgo</th></tr></thead>
<tbody>
{chr(10).join(filas)}
</tbody></table></div>
<p class="foot">El histórico comienza el 8 de octubre de 2026. Reserva: reserva útil del SIN en % de la capacidad. Aportes: promedio acumulado del mes frente a la media histórica de XM. Fuente: XM S.A. E.S.P. © Ing. Alejandro Aroca · IA HSIN Colombia.</p>
</main>
<script data-goatcounter="https://arcomisp.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</body></html>
'''
    open(os.path.join("historico", "index.html"), "w", encoding="utf-8").write(page)


if __name__ == "__main__":
    archivar(sys.argv[1])
    indice()

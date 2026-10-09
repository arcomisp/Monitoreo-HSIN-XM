#!/usr/bin/env python3
"""Convierte la salida JSON de xm_brief.py en un brief en Markdown con alertas por reglas.
Uso: python3 brief_md.py xm.json > brief.md
     python3 brief_md.py xm.json --html > brief.html   (fragmento HTML para la portada)"""
import html, json, re, sys


def md_to_html(md):
    """Convierte el subconjunto de Markdown que produce este script (títulos, tablas, listas, negrita, cursiva)."""
    def inline(t):
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        return re.sub(r"(?<![\w])_(.+?)_(?![\w])", r"<i>\1</i>", t)
    out, rows, items = [], [], []

    def flush():
        if rows:
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows if not re.match(r"^\|[-:| ]+\|$", r)]
            h = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
            b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
            out.append(f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")
            rows.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
    for line in md.splitlines():
        if line.startswith("|"):
            rows.append(line); continue
        if line.startswith("- "):
            items.append(line[2:]); continue
        flush()
        if line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    flush()
    return "\n".join(out)


def f(x, n=2):
    return "—" if x is None else f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main(path):
    d = json.load(open(path, encoding="utf-8"))
    ap, ant, r = d["aportes_mes"], d["aportes_mes_anterior"], d["reservas"]
    sin = ap["SIN"]
    L = [f"# Brief hidrológico SIN · corte {d['corte_aportes']}", "",
         f"**Aportes SIN del mes: {f(sin['pct'])} %** de la media histórica "
         f"({f(sin['real_gwh_dia'],1)} de {f(sin['hist_gwh_dia'],1)} GWh/día, {d['dias_mes']} días) · "
         f"**Reservas: {f(r['pct'])} %** ({f(r['gwh'],0)} GWh) al {r['fecha']}", "",
         "## Aportes por región (promedio acumulado del mes)", "",
         "| Región | Real GWh/día | Media hist. GWh/día | % mes | % sin desviaciones | % mes anterior |",
         "|---|---:|---:|---:|---:|---:|"]
    regs = sorted([k for k in ap if k != "SIN"], key=lambda k: ap[k]["pct"] or 0)
    for k in regs + ["SIN"]:
        v = ap[k]
        L.append(f"| {k.title() if k != 'SIN' else '**SIN**'} | {f(v['real_gwh_dia'])} | {f(v['hist_gwh_dia'])} | "
                 f"{f(v['pct'])} | {f(v.get('pct_sin_desviaciones'))} | {f(ant[k]['pct'])} |")
    L += ["", "## Reservas del SIN", "",
          f"- Nivel: **{f(r['pct'])} %** · {f(r['gwh'],1)} de {f(r['cap_gwh'],1)} GWh de capacidad útil",
          f"- Frente al cierre del mes anterior: {f(r['var_pp_vs_cierre'])} pp · {f(r['var_gwh_vs_cierre'],1)} GWh",
          f"- Frente a ayer: {f(r['var_pp_vs_ayer'])} pp · en 7 días: {f(r['var_pp_7d'])} pp",
          f"- Senda de Referencia del día: {f(r['senda_referencia_pct'])} % · brecha **{f(r['brecha_vs_senda_pp'])} pp** · "
          f"senda a fin de mes: {f(r['senda_fin_de_mes_pct'])} %",
          f"- CAR: {f(r['car_pct'])} % · margen {f(None if r['car_pct'] is None else r['pct'] - r['car_pct'])} pp",
          "- Por región: " + " · ".join(f"{k.title()} {f(v['pct'],1)} %" for k, v in d["reservas_region"].items()),
          "", f"## Vertimientos", "",
          f"- Mes: {f(d['vertimientos_mes_gwh'],1)} GWh · último día: {f(d['vertimientos_ultimo_dia_gwh'],2)} GWh", ""]
    al = []
    for k in regs:
        if (ap[k]["pct"] or 999) < 60:
            al.append(f"{k.title()}: aportes en {f(ap[k]['pct'],1)} % de la media")
    if sin["pct"] < 80:
        al.append(f"Aportes SIN en {f(sin['pct'],1)} % (< 80 %)")
    if r["brecha_vs_senda_pp"] is not None and r["brecha_vs_senda_pp"] < -2:
        al.append(f"Reservas {f(-r['brecha_vs_senda_pp'])} pp por debajo de la senda")
    if r["var_pp_7d"] is not None and r["var_pp_7d"] < -1:
        al.append(f"Caída de reservas de {f(-r['var_pp_7d'])} pp en 7 días")
    if d["vertimientos_mes_gwh"] > 1 and r["pct"] < 80:
        al.append(f"Vertimientos de {f(d['vertimientos_mes_gwh'],1)} GWh en el mes con reservas del SIN por debajo de 80 %")
    if r["car_pct"] is not None and r["pct"] - r["car_pct"] < 10:
        al.append("Reservas a menos de 10 pp de la CAR")
    if r["senda_referencia_pct"] is None:
        al.append("Fuera del horizonte de la Senda de Referencia: cargar la nueva senda de XM")
    L += ["## Alertas", ""] + ([f"- ⚠️ {a}" for a in al] or ["- Sin alertas"]) + [""]
    L.append("_Fuente: API pública de XM (servapibi.xm.com.co). Datos sujetos a revisión por XM._")
    md = "\n".join(L)
    print(md_to_html(md) if "--html" in sys.argv else md)


if __name__ == "__main__":
    main(sys.argv[1])

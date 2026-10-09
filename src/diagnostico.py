#!/usr/bin/env python3
"""Conclusión del día en lenguaje sencillo, a partir de la salida de xm_brief.py.
Uso: python3 diagnostico.py xm.json [--md] > reportes/DIAGNOSTICO.html
Reglas fijas y transparentes (no es un pronóstico):
  ALTO      margen sobre la CAR < 10 pp, o reservas más de 8 pp bajo la Senda de Referencia
  MODERADO  reservas más de 2 pp bajo la senda, o aportes del mes < 70 % de la media, o margen sobre la CAR < 20 pp
  BAJO      en los demás casos
"""
import calendar, datetime as dt, html, json, sys

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
REG = {"ANTIOQUIA": "Antioquia", "CALDAS": "Caldas", "CARIBE": "Caribe", "CENTRO": "Centro", "ORIENTE": "Oriente", "VALLE": "Valle"}


def n(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fecha(s):
    d = dt.date.fromisoformat(s)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def main(path, md=False):
    j = json.load(open(path, encoding="utf-8"))
    r, ap = j["reservas"], j["aportes_mes"]
    corte = dt.date.fromisoformat(r["fecha"])
    pct, cap = r["pct"], r["cap_gwh"]
    car, senda, senda_fm = r.get("car_pct"), r.get("senda_referencia_pct"), r.get("senda_fin_de_mes_pct")
    margen = pct - car if car is not None else None
    brecha = r.get("brecha_vs_senda_pp")
    sin = ap["SIN"]["pct"]
    regs = sorted([k for k in ap if k != "SIN"], key=lambda k: ap[k]["pct"])
    peor, mejor = regs[0], regs[-1]
    v7 = r.get("var_pp_7d")
    dd = j.get("aportes_diarios_sin", [])

    # nivel de riesgo
    if (margen is not None and margen < 10) or (brecha is not None and brecha < -8):
        nivel, color = "ALTO", "alto"
    elif (brecha is not None and brecha < -2) or sin < 70 or (margen is not None and margen < 20):
        nivel, color = "MODERADO", "moderado"
    else:
        nivel, color = "BAJO", "bajo"

    p = []
    # 1. cuánta agua hay
    t = f"Los embalses del país tienen hoy agua equivalente al {n(pct)} % de su capacidad ({n(r['gwh'], 0)} GWh)."
    if margen is not None:
        t += f" Esto está {n(margen)} puntos por encima del nivel mínimo de seguridad que vigila el regulador (CAR, {n(car)} %)"
    if brecha is not None:
        t += f" y {n(abs(brecha))} puntos {'por debajo' if brecha < 0 else 'por encima'} de la meta planeada para esta fecha (Senda de Referencia, {n(senda)} %)."
    else:
        t += "."
    p.append(("¿Cuánta agua hay?", t))

    # 2. cuánta agua está llegando
    t = (f"Los ríos están trayendo menos agua de lo normal: en lo que va de {MESES[corte.month - 1]} llega el {n(sin, 0)} % de lo habitual para estos días."
         if sin < 95 else f"Los ríos traen un volumen cercano o superior a lo normal: {n(sin, 0)} % de lo habitual en lo que va de {MESES[corte.month - 1]}.")
    t += (f" La región más afectada es {REG[peor]} ({n(ap[peor]['pct'], 0)} %)"
          + (", la de mayor peso en el sistema" if peor == "ANTIOQUIA" else "")
          + f", y la mejor es {REG[mejor]} ({n(ap[mejor]['pct'], 0)} %).")
    if len(dd) >= 4:
        ult = dd[-1]["pct"]; minimo = min(x["pct"] for x in dd)
        if ult > minimo + 5:
            t += f" Hay una señal positiva: el aporte diario del sistema subió de un mínimo de {n(minimo, 0)} % a {n(ult, 0)} % en los últimos días. Aún no es una tendencia, pero va en la dirección correcta."
        elif ult < dd[-4]["pct"] - 5:
            t += f" En los últimos días los aportes siguen bajando (hoy {n(ult, 0)} % de lo normal)."
    p.append(("¿Cuánta agua está llegando?", t))

    # 3. hacia dónde va
    t = ""
    if v7 is not None:
        t += (f"En la última semana las reservas {'bajaron' if v7 < 0 else 'subieron'} {n(abs(v7))} puntos. ")
    if senda_fm is not None:
        fin = dt.date(corte.year, corte.month, calendar.monthrange(corte.year, corte.month)[1])
        dias = (fin - corte).days
        falta = (senda_fm - pct) / 100 * cap
        if falta > 0 and dias > 0:
            t += (f"Para llegar a la meta de fin de mes ({n(senda_fm)} % el {fecha(fin.isoformat())}), los embalses necesitarían ganar unos {n(falta, 0)} GWh "
                  f"en {dias} días, es decir, recibir más agua de la que se usa para generar energía. Eso depende de que las lluvias se fortalezcan.")
        elif falta <= 0:
            t += f"Las reservas ya están por encima de la meta de fin de mes ({n(senda_fm)} %)."
    else:
        t += "La Senda de Referencia vigente terminó su horizonte; se usará la nueva senda cuando XM la publique."
    p.append(("¿Hacia dónde va?", t.strip()))

    # 4. diagnóstico
    expl = {
        "BAJO": "El sistema tiene agua suficiente y avanza según lo planeado. No hay señales de riesgo para el abastecimiento de energía.",
        "MODERADO": "No hay riesgo inmediato para el abastecimiento de energía: los embalses tienen un margen amplio sobre el nivel de seguridad. "
                    "Pero las lluvias están por debajo de lo normal y las reservas no alcanzan la meta planeada, así que conviene vigilar la evolución "
                    "y prepararse con medidas preventivas (uso eficiente de la energía, disponibilidad de generación térmica y de gas), sin alarma.",
        "ALTO": "Las reservas están cerca del nivel mínimo de seguridad o muy por debajo de lo planeado. Se justifican medidas preventivas firmes y una comunicación clara al país.",
    }[nivel]
    p.append((f"Diagnóstico del día: riesgo {nivel}", expl))

    nota = ("Conclusión generada automáticamente con datos oficiales de XM y reglas fijas: riesgo ALTO si el margen sobre la CAR es menor a 10 puntos "
            "o las reservas están más de 8 puntos bajo la senda; MODERADO si están más de 2 puntos bajo la senda, los aportes del mes son menores al 70 % "
            "de lo normal o el margen sobre la CAR es menor a 20 puntos; BAJO en los demás casos. No es un pronóstico.")

    if md:
        out = [f"# Conclusión del día · {fecha(r['fecha'])}", "", f"**Nivel de riesgo: {nivel}**", ""]
        for h, t in p:
            out += [f"## {h}", "", t, ""]
        out.append(f"_{nota}_")
        print("\n".join(out))
        return
    e = html.escape
    out = [f'<div class="dx-head"><span class="dx-fecha">Corte: {e(fecha(r["fecha"]))}</span>'
           f'<span class="dx-nivel dx-{color}">Riesgo {nivel}</span></div>']
    for h, t in p:
        cls = ' class="dx-final"' if h.startswith("Diagnóstico") else ""
        out.append(f"<div{cls}><h3>{e(h)}</h3><p>{e(t)}</p></div>")
    out.append(f'<p class="dx-nota">{e(nota)}</p>')
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1], "--md" in sys.argv)

#!/usr/bin/env python3
"""Conclusión del día en lenguaje sencillo, a partir de la salida de xm_brief.py.
Uso: python3 diagnostico.py xm.json [--md] [--tablero index.html] > reportes/DIAGNOSTICO.html
(--tablero: lee del tablero ya actualizado los datos de generación térmica)
Reglas fijas y transparentes (no es un pronóstico):
  ALTO      margen sobre la CAR < 10 pp, o reservas más de 8 pp bajo la Senda de Referencia
  MODERADO  reservas más de 2 pp bajo la senda, o aportes del mes < 70 % de la media, o margen sobre la CAR < 20 pp
  BAJO      en los demás casos
"""
import calendar, datetime as dt, html, json, os, sys

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
REG = {"ANTIOQUIA": "Antioquia", "CALDAS": "Caldas", "CARIBE": "Caribe", "CENTRO": "Centro", "ORIENTE": "Oriente", "VALLE": "Valle"}


def n(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fecha(s):
    d = dt.date.fromisoformat(s)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def dna_30d(corte):
    """DNA de los últimos 30 días (GWh y % de la demanda). Devuelve None si la API no responde."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from xm_brief import daily
        d0 = corte - dt.timedelta(days=29)
        p = daily("DemaNoAtenProg", "Area", d0, corte)
        n = daily("DemaNoAtenNoProg", "Area", d0, corte)
        dem = daily("DemaSIN", "Sistema", d0, corte)
        g = (sum(sum(v.values()) for v in p.values()) + sum(sum(v.values()) for v in n.values())) / 1e6
        m = sum(sum(v.values()) for v in dem.values()) / 1e6
        return g, (100 * g / m if m else None)
    except Exception:
        return None


def tablero_D(path):
    """Datos (const D) del tablero index.html ya actualizado. {} si no se pueden leer."""
    try:
        s = open(path, encoding="utf-8").read()
        i = s.index("const D=") + 8
        return json.JSONDecoder().raw_decode(s[i:])[0]
    except Exception:
        return {}


def texto_termicas(T, pct, sin):
    u = T["u7"]
    M = T["mensual"]
    mn = M[-1]
    ter = lambda m: m[3] + m[4] + m[5] + m[6]
    uso = 100 * u["gen_mw"] / u["dispo_mw"] if u.get("dispo_mw") else None
    t = (f"En la última semana las plantas térmicas generaron {n(u['gwh_dia'])} GWh por día, el {n(u['pct'], 0)} % de la energía del país "
         f"(en enero era el {n(100 * ter(M[0]) / M[0][2], 0)} %). Mientras más energía aportan las térmicas, menos agua se saca de los embalses.")
    if uso is not None:
        if uso >= 95:
            t += f" Están entregando el {n(uso, 0)} % de lo que tienen disponible: prácticamente al tope, sin margen térmico adicional."
        elif uso >= 80:
            t += f" Están entregando el {n(uso, 0)} % de lo que tienen disponible: queda un margen pequeño."
        else:
            t += f" Están entregando el {n(uso, 0)} % de lo que tienen disponible: hay margen para generar más con térmicas y cuidar el agua."
    # disponibilidad: últimos 7 días frente a un mes antes
    dd = [r for r in T.get("diario", []) if r[2]]
    if len(dd) >= 37:
        a = sum(r[2] for r in dd[-7:]) / 7
        b = sum(r[2] for r in dd[-37:-30]) / 7
        if a < 0.9 * b:
            t += f" La potencia térmica disponible bajó de unos {n(b, 0)} MW hace un mes a {n(a, 0)} MW, lo que reduce el respaldo."
        elif a > 1.1 * b:
            t += f" La potencia térmica disponible subió de unos {n(b, 0)} MW hace un mes a {n(a, 0)} MW, lo que fortalece el respaldo."
    if len(M) >= 4 and mn[5] > 2 and mn[5] > 2 * M[-4][5]:
        t += (f" El uso de combustibles líquidos (ACPM, combustóleo, jet), los más costosos, subió a {n(mn[5])} GWh por día, "
              f"frente a {n(M[-4][5])} hace tres meses: suele indicar que el gas disponible no alcanza y presiona al alza el precio de la energía.")
    fm = sum(r[2] for r in T.get("fuera", []))
    if fm >= 50:
        nombres = ", ".join(r[0] for r in T["fuera"][:3])
        t += f" Hay {n(fm, 0)} MW térmicos sin disponibilidad (entre ellos {nombres})."
    if uso is not None and uso < 90 and sin < 80 and pct >= 70:
        t += " Con lluvias bajas y embalses aún altos, es un buen momento para generar más con térmicas y guardar agua para el verano."
    elif uso is not None and uso >= 95 and sin < 80:
        t += " Como las térmicas ya dan todo lo que pueden, cuidar el agua depende ahora de recuperar las plantas fuera de servicio y de asegurar el gas."
    return t


def ritmo_gwh_7d(r):
    """Descenso medio de las reservas en GWh/día en los últimos 7 días (positivo = bajan). No depende de cambios de capacidad útil."""
    h = r.get("hace_7_dias") or {}
    return (h["gwh"] - r["gwh"]) / 7 if h.get("gwh") else None


def potencial_termico(T, factor=0.9):
    fm = sum(x[2] for x in T.get("fuera", []))
    return fm, fm * 24 * factor / 1000


def texto_positivo(T, r, meta=95.0):
    """Conclusión positiva: cuánta agua se ahorraría si regresan las térmicas sin disponibilidad."""
    fm, pot = potencial_termico(T)
    cap = r["cap_gwh"]
    if fm < 50 or not cap:
        return None
    pp_dia = pot / (cap / 100)
    t = (f"Hay respaldo que se puede recuperar. Si regresan las {len(T['fuera'])} plantas térmicas hoy sin disponibilidad ({n(fm, 0)} MW), "
         f"podrían aportar unos {n(pot, 0)} GWh por día (suponiendo que operen al 90 %). Esa energía dejaría de salir de los embalses: "
         f"equivale a ahorrar cerca de {n(pp_dia, 2)} puntos de reserva por día, unos {n(30 * pp_dia)} puntos por mes.")
    caida = ritmo_gwh_7d(r)
    if caida is not None and caida > 0:
        if pot >= caida:
            t += (f" Es más que lo que están bajando hoy los embalses ({n(caida, 0)} GWh por día en la última semana): "
                  "con esas plantas de vuelta, las reservas dejarían de caer al ritmo actual.")
        else:
            t += (f" Con eso, la caída de los embalses ({n(caida, 0)} GWh por día en la última semana) se reduciría en {n(100 * pot / caida, 0)} %.")
    g = T["u7"]["gwh_dia"]
    if g < meta <= g + pot:
        t += f" Además, la generación térmica pasaría de {n(g)} a unos {n(g + pot, 0)} GWh por día y superaría la meta de {n(meta, 0)} GWh por día fijada para El Niño."
    t += " Las térmicas no reemplazan la lluvia, pero sí ganan tiempo y protegen las reservas para el verano."
    return t


def escenario_adverso(D, r, T):
    """Escenario adverso (no es pronóstico): las reservas bajan todos los días al ritmo de la peor semana de los últimos 30 días.
    Muestra el nivel al cierre del horizonte (30 de noviembre, inicio del verano) con y sin las medidas, en orden de prioridad."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from update_dashboard import CAR
    g = [(x[0], x[4]) for x in D.get("daily", []) if x[4]]
    if len(g) < 40:
        return None
    pasos = [(g[k][0], (g[k - 7][1] - g[k][1]) / 7) for k in range(len(g) - 30, len(g))]
    fsem, ritmo = max(pasos, key=lambda z: z[1])
    if ritmo <= 0:
        return None
    E, cap = r["gwh"], r["cap_gwh"]
    d0 = dt.date.fromisoformat(r["fecha"])
    fin = dt.date(d0.year, 11, 30)
    if (fin - d0).days < 15:
        fin = min(d0 + dt.timedelta(days=45), dt.date(d0.year, 12, 27))
    dias = (fin - d0).days
    car_fin = CAR.get(str(fin.isocalendar()[1]))
    nivel = lambda rt: max(0.0, (E - rt * dias) / cap * 100)
    dem = T["mensual"][-1][2] if T and T.get("mensual") else 250.0  # GWh/día de generación ≈ demanda
    pot = potencial_termico(T)[1] if T else 0.0
    vol, rac = 0.02 * dem, 0.05 * dem
    def vs_car(x):
        if car_fin is None:
            return ""
        dif = x - car_fin
        return f", {n(abs(dif))} puntos {'por encima' if dif >= 0 else 'por debajo'} de la CAR"
    b0 = nivel(ritmo)
    intro = (f"Si las lluvias no llegan y los embalses bajaran todos los días al ritmo de la peor semana del último mes "
             f"({n(ritmo, 0)} GWh por día, semana al {fecha(fsem)}), llegarían al {fecha(fin.isoformat())}, inicio del verano, con {n(b0)} %"
             f"{vs_car(b0)} ({n(car_fin)} % en esa fecha). Es un escenario de cautela, no un pronóstico. "
             "Las medidas, en orden de prioridad, y el nivel con que llegarían los embalses a esa fecha:" if car_fin else
             f"Si las lluvias no llegan y los embalses bajaran al ritmo de la peor semana del último mes ({n(ritmo, 0)} GWh por día), "
             f"llegarían al {fecha(fin.isoformat())} con {n(b0)} %. Es un escenario de cautela, no un pronóstico. Las medidas, en orden de prioridad:")
    items, acum = [], 0.0
    pasos_m = []
    if pot > 0:
        pasos_m.append((pot, f"Recuperar las térmicas paradas (unos {n(pot, 0)} GWh por día)"))
    pasos_m.append((vol, f"Que el programa de ahorro de la CREG (resoluciones 101 120 y 101 126 de 2026), vigente desde septiembre, logre un ahorro del 2 % de la demanda (unos {n(vol, 0)} GWh por día)"))
    pasos_m.append((rac, f"Solo como último recurso, racionamiento programado del 5 %, anunciado y por horarios y sectores (unos {n(rac, 0)} GWh por día)"))
    for k, (gw, txt) in enumerate(pasos_m, 1):
        acum += gw
        x = nivel(ritmo - acum)
        items.append(f"{k}. {txt}: {n(x)} %{vs_car(x)}.")
    margen = r["pct"] - (r.get("car_pct") or 0)
    cierre = (f"Hoy no se requiere racionamiento: las reservas están {n(margen)} puntos por encima de la CAR. "
              "El escenario muestra que la prioridad es recuperar las térmicas y que el programa de ahorro de la CREG dé resultados, para no tener que llegar a cortes programados.")
    return [intro] + items + [cierre]


def main(path, md=False, tablero=None):
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

    # 3b. ¿la energía está llegando a los usuarios?
    dn = dna_30d(corte)
    if dn and dn[1] is not None:
        g, pc = dn
        if pc < 0.3:
            t = (f"En los últimos 30 días la demanda no atendida fue de {n(g)} GWh, el {n(pc, 2)} % de la demanda del país, un nivel normal. "
                 "Es el nivel típico de eventos y restricciones en las redes (fallas, mantenimientos, equipos al límite) "
                 "y no muestra señales de cortes por escasez de agua.")
        else:
            t = (f"En los últimos 30 días la demanda no atendida fue de {n(g)} GWh, el {n(pc, 2)} % de la demanda del país, por encima de lo normal. "
                 "Conviene revisar sus causas en los reportes de XM para descartar que se deba a falta de energía.")
        p.append(("¿La energía está llegando a los usuarios?", t))

    # 3c. térmicas
    DT = tablero_D(tablero) if tablero else {}
    T = DT.get("ter")
    if T and T.get("u7") and T.get("mensual"):
        try:
            p.append(("¿Cómo están ayudando las térmicas?", texto_termicas(T, pct, sin)))
            tp = texto_positivo(T, r)
            if tp:
                p.append(("Una señal positiva: el respaldo que se puede recuperar", tp))
        except Exception:
            pass

    if DT:
        try:
            ea = escenario_adverso(DT, r, T)
            if ea:
                p.append(("Si las lluvias no llegan: escenario adverso y medidas", ea))
        except Exception:
            pass

    # la DNA va al final, justo antes del diagnóstico
    p.sort(key=lambda x: x[0].startswith("¿La energía"))

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
            out += [f"## {h}", ""] + ([x for y in t for x in (y, "")] if isinstance(t, list) else [t, ""])
        out.append(f"_{nota}_")
        print("\n".join(out))
        return
    e = html.escape
    out = [f'<div class="dx-head"><span class="dx-nivel dx-{color}">Riesgo {nivel}</span>'
           f'<span class="dx-fecha">Corte: {e(fecha(r["fecha"]))}</span></div>']
    for h, t in p:
        cls = ' class="dx-final"' if h.startswith("Diagnóstico") else ""
        if isinstance(t, list):
            li = [x for x in t if x[:1].isdigit()]
            body = (f"<p>{e(t[0])}</p><ol>" + "".join(f"<li>{e(x.split('. ', 1)[1])}</li>" for x in li) + "</ol>"
                    + "".join(f"<p>{e(x)}</p>" for x in t[1:] if x not in li))
        else:
            body = f"<p>{e(t)}</p>"
        out.append(f"<div{cls}><h3>{e(h)}</h3>{body}</div>")
    out.append(f'<p class="dx-nota">{e(nota)}</p>')
    print("\n".join(out))


if __name__ == "__main__":
    a = sys.argv
    main(a[1], "--md" in a, a[a.index("--tablero") + 1] if "--tablero" in a else None)

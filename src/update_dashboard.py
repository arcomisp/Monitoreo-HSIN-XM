#!/usr/bin/env python3
"""Actualiza los datos (const D) del tablero 'Senda Hídrica del SIN 2026' con la API de XM.
Uso: python3 update_dashboard.py <html_entrada> <html_salida>"""
import json, re, sys, datetime as dt, urllib.request

API = "https://servapibi.xm.com.co"
REG = ["ANTIOQUIA", "CALDAS", "CARIBE", "CENTRO", "ORIENTE", "VALLE"]
DESV_NAT = ["DESV. BATATAS", "DESV. CHIVOR", "DESV. EEPPM (NEC,PAJ,DOL)"]  # excluidas en Aportes Naturales
TOP_VERT = ["ITUANGO", "GUAVIO", "ESMERALDA"]
CAR = {"1": 59.83, "2": 58.01, "3": 55.7, "4": 52.91, "5": 50.33, "6": 47.12, "7": 44.6, "8": 42.18, "9": 40.35, "10": 38.48, "11": 36.57, "12": 34.53, "13": 33.57, "14": 32.34, "15": 31.59, "16": 30.62, "17": 30.28, "18": 31.21, "19": 32.16, "20": 33.19, "21": 33.53, "22": 35.49, "23": 37.22, "24": 38.84, "25": 40.1, "26": 42.71, "27": 44.17, "28": 45.69, "29": 47.97, "30": 48.9, "31": 49.58, "32": 49.97, "33": 50.85, "34": 51.34, "35": 51.91, "36": 52.26, "37": 52.67, "38": 52.97, "39": 52.47, "40": 52.38, "41": 51.98, "42": 53.13, "43": 54.21, "44": 55.44, "45": 56.6, "46": 59.23, "47": 61.95, "48": 63.23, "49": 62.87, "50": 62.13, "51": 62.04, "52": 60.86}
# Escenario hidrológico de la senda (min, prom, max GWh/día) por semana
ESC = {"2026-10-05": [75.9, 193.9, 334.3], "2026-10-12": [88.9, 198.5, 325.4], "2026-10-19": [109.9, 204.9, 342.9], "2026-10-26": [120.8, 219.8, 372.6], "2026-11-02": [137.2, 217.9, 337.1], "2026-11-09": [132.5, 221.5, 321.3], "2026-11-16": [106.7, 198.7, 301.0], "2026-11-23": [110.6, 184.0, 283.2], "2026-11-30": [89.3, 164.1, 244.0], "2026-12-07": [74.3, 150.5, 223.6], "2026-12-14": [95.2, 141.1, 203.9], "2026-12-21": [79.5, 122.1, 176.5], "2026-12-28": [66.2, 112.4, 170]}


def post(path, body):
    req = urllib.request.Request(API + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    err = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            err = e
    raise err


def daily(metric, entity, d0, d1):
    out, a = {}, d0
    while a <= d1:
        b = min(a + dt.timedelta(days=27), d1)
        js = post("/daily", {"MetricId": metric, "StartDate": a.isoformat(), "EndDate": b.isoformat(), "Entity": entity})
        for it in js.get("Items", []):
            for e in it["DailyEntities"]:
                if e.get("Value") in (None, ""):
                    continue
                out.setdefault(it["Date"], {})[e.get("Name") or e.get("Id")] = float(e["Value"]) / 1e6  # GWh
        a = b + dt.timedelta(days=1)
    return out


def region_map(metric="ListadoRios"):
    js = post("/lists", {"MetricId": metric})
    m = {e["Values"]["Name"]: e["Values"]["HydroRegion"] for it in js["Items"] for e in it["ListEntities"]}
    if metric == "ListadoRios":
        m.setdefault("AMOYA", "CENTRO")
    return m


def reservas_region(day, emap):
    k = day.isoformat()
    vol = daily("VoluUtilDiarEner", "Embalse", day, day).get(k, {})
    cap = daily("CapaUtilDiarEner", "Embalse", day, day).get(k, {})
    agg = {r: [0.0, 0.0] for r in REG}
    for name, v in vol.items():
        r = emap.get(name)
        if r in agg and name in cap:
            agg[r][0] += v
            agg[r][1] += cap[name]
    return agg


def eom(y, m):
    return (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))


LIQ = {"ACPM", "COMBUSTOLEO", "JET-A1", "GLP"}


def hourly_rec(metric, d0, d1):
    """Suma diaria (MWh) por recurso de una métrica horaria de XM."""
    out, a = {}, d0
    while a <= d1:
        b = min(a + dt.timedelta(days=27), d1)
        js = post("/hourly", {"MetricId": metric, "StartDate": a.isoformat(), "EndDate": b.isoformat(), "Entity": "Recurso"})
        for it in js.get("Items", []):
            for h in it["HourlyEntities"]:
                v = h["Values"]
                c = v.get("code") or v.get("Code")
                hs = [float(v[k]) for k in v if k.startswith("Hour") and v[k] not in (None, "")]
                if c and hs:
                    out.setdefault(it["Date"], {})[c] = sum(hs) / 1e3
        a = b + dt.timedelta(days=1)
    return out


def termicas(D, hoy):
    """Generación térmica: mensual por combustible, uso de la disponibilidad y plantas sin disponibilidad."""
    js = post("/lists", {"MetricId": "ListadoRecursos", "StartDate": hoy.isoformat(), "EndDate": hoy.isoformat(), "Entity": "Sistema"})
    rec = {x["Values"]["Code"]: x["Values"] for i in js["Items"] for x in i["ListEntities"]}
    ter = {c: v for c, v in rec.items() if (v.get("Type") or "").upper() == "TERMICA"}
    desp = {c for c, v in ter.items() if (v.get("Disp") or "").startswith("DESPACHADO")}
    T = D.get("ter") or {}
    d0 = dt.date(hoy.year, 1, 1)
    if T.get("mensual"):
        pm = dt.date(hoy.year, hoy.month, 1) - dt.timedelta(days=1)
        d0 = max(d0, dt.date(pm.year, pm.month, 1))
    G, Dp = hourly_rec("Gene", d0, hoy), hourly_rec("DispoReal", d0, hoy)
    dias = sorted(G)
    if not dias:
        return
    def grupo(c):
        f = ter[c].get("EnerSource", "")
        return "gas" if f == "GAS" else "carbon" if f == "CARBON" else "liq" if f in LIQ else "otros"
    mens = {r[0]: r for r in T.get("mensual", [])}
    acc = {}
    for d in dias:
        a = acc.setdefault(d[:7], {"n": 0, "tot": 0.0, "gas": 0.0, "carbon": 0.0, "liq": 0.0, "otros": 0.0})
        a["n"] += 1
        for c, x in G[d].items():
            a["tot"] += x
            if c in ter:
                a[grupo(c)] += x
    for m, a in acc.items():
        n = a["n"]
        mens[m] = [m, n, round(a["tot"] / n / 1e3, 2)] + [round(a[k] / n / 1e3, 2) for k in ("gas", "carbon", "liq", "otros")]
    # serie diaria (últimos 60 días): generación y disponibilidad de las térmicas despachadas centralmente, en MW medios
    dia = {r[0]: r for r in T.get("diario", [])}
    for d in dias:
        g = sum(x for c, x in G[d].items() if c in desp)
        dp = sum(x for c, x in Dp.get(d, {}).items() if c in desp)
        tg = sum(x for c, x in G[d].items() if c in ter)
        dia[d] = [d, round(g / 24), round(dp / 24), round(tg / 1e3, 2)]
    diario = [dia[k] for k in sorted(dia)][-60:]
    # capacidad máxima observada (MW) por planta despachada, conservada entre corridas
    mx = T.get("maxmw", {})
    for d, v in Dp.items():
        for c, x in v.items():
            if c in desp:
                mx[c] = max(mx.get(c, 0), round(x / 24))
    u7 = dias[-7:]
    gen7 = {c: sum(G[d].get(c, 0) for d in u7) / len(u7) / 24 for c in desp}
    dis7 = {c: sum(Dp.get(d, {}).get(c, 0) for d in u7) / len(u7) / 24 for c in desp}
    nom = lambda c: ter[c]["Name"].title().replace("Cc", "CC").replace("Tebsab", "TEBSA").replace("Zipaemg", "Zipa")
    fuel = lambda c: ter[c].get("EnerSource", "").capitalize().replace("Carbon", "Carbón").replace("Combustoleo", "Combustóleo").replace("Acpm", "ACPM").replace("Jet-a1", "Jet A1").replace("Glp", "GLP")
    top = [[nom(c), fuel(c), round(gen7[c]), round(dis7[c])] for c in sorted(desp, key=lambda c: -gen7[c])[:12]]
    fuera = [[nom(c), fuel(c), mx[c], round(dis7.get(c, 0))] for c in sorted(mx, key=lambda c: -mx[c])
             if c in desp and mx[c] >= 20 and dis7.get(c, 0) < 0.2 * mx[c]]
    tot7 = sum(sum(G[d].values()) for d in u7)
    ter7 = sum(sum(x for c, x in G[d].items() if c in ter) for d in u7)
    D["ter"] = {"fecha": dias[-1], "mensual": [mens[k] for k in sorted(mens)], "diario": diario, "maxmw": mx,
                "top": top, "fuera": fuera,
                "u7": {"gwh_dia": round(ter7 / len(u7) / 1e3, 1), "pct": round(100 * ter7 / tot7, 1),
                       "gen_mw": round(sum(gen7.values())), "dispo_mw": round(sum(dis7.values()))}}


def main(src, dst):
    s = open(src, encoding="utf-8").read()
    mt = re.search(r"const D=(\{.*?\});\n", s, re.S)
    D = json.loads(mt.group(1))
    hoy = dt.date.today()
    jan1 = dt.date(hoy.year if hoy.month > 1 or hoy.day > 7 else hoy.year - 1, 1, 1)

    # --- Reservas (todo el año: sirve para diario y cortes)
    vol = daily("VoluUtilDiarEner", "Sistema", jan1, hoy)
    cap = daily("CapaUtilDiarEner", "Sistema", jan1, hoy)
    res = {d: (sum(vol[d].values()), sum(cap[d].values())) for d in vol if d in cap}
    last = max(res)
    L = dt.date.fromisoformat(last)

    # --- Vertimientos por embalse
    V = daily("VertEner", "Embalse", jan1, L)
    nmes = L.month
    ser = {k: [0.0] * nmes for k in TOP_VERT + ["OTROS"]}
    for d, v in V.items():
        m = int(d[5:7]) - 1
        if m < nmes:
            for k, val in v.items():
                ser[k if k in ser else "OTROS"][m] += val
    cumv = sum(sum(v.values()) for d, v in V.items() if d <= last)
    D["vert"] = {"meses": list(range(1, nmes + 1)), "series": {k: [round(x, 1) for x in v] for k, v in ser.items()}, "total": round(cumv, 1)}

    # --- Diario: refresca días con datos y agrega días nuevos
    rows = {r[0]: r for r in D["daily"]}
    d = jan1
    while d <= L:
        k = d.isoformat()
        if k in res:
            g, c = res[k]
            if k not in rows:
                rows[k] = [k, None, None, CAR.get(str(d.isocalendar()[1])), None, None]
            r = rows[k]
            r[1], r[4] = round(100 * g / c, 2), round(g, 1)
            cv = sum(sum(v.values()) for dd, v in V.items() if dd <= k)
            r[5] = round(min(100.0, (g + cv) / c * 100), 2)
        d += dt.timedelta(days=1)
    D["daily"] = [rows[k] for k in sorted(rows)]

    # --- Cortes de fin de mes (+ corte parcial)
    cuts, prev = [], None
    for m in range(1, L.month + 1):
        fe = eom(L.year, m)
        k = (fe if fe <= L else L).isoformat()
        if k not in res:
            continue
        g, c = res[k]
        pct = round(100 * g / c, 2)
        parcial = fe > L
        vm = None if parcial else round(sum(ser[x][m - 1] for x in ser), 1)
        cuts.append([k, round(g, 1), round(c, 1), pct, None if prev is None else round(pct - prev[3], 2),
                     None if prev is None else round(g - prev[1], 1), vm])
        prev = cuts[-1]
    D["cuts"] = cuts

    # --- Aportes: mes actual y anterior (regiones y SIN), series diarias
    rm = region_map()
    ini_prev = (L.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    R = daily("AporEner", "Rio", ini_prev, L)
    H = daily("AporEnerMediHist", "Rio", ini_prev, L)
    ap_days = sorted(R)
    corte_ap = ap_days[-1]
    CA = dt.date.fromisoformat(corte_ap)
    for mdate in sorted({x[:7] for x in ap_days}):
        days = [x for x in ap_days if x.startswith(mdate)]
        mi = int(mdate[5:]) - 1
        a, h = {}, {}
        for x in days:
            for n, v in R[x].items():
                a[rm.get(n)] = a.get(rm.get(n), 0) + v
            for n, v in H.get(x, {}).items():
                h[rm.get(n)] = h.get(rm.get(n), 0) + v
        nd = len(days)
        for g in REG:
            while len(D["heat"][g]) <= mi:
                D["heat"][g].append(None)
            D["heat"][g][mi] = [round(100 * a.get(g, 0) / h[g], 2), round(a.get(g, 0) / nd, 2), round(h[g] / nd, 2)]
        sinr = sum(sum(R[x].values()) for x in days) / nd
        while len(D["heat"]["SIN"]) <= mi:
            D["heat"]["SIN"].append(None)
        old = D["heat"]["SIN"][mi]
        sinh = old[2] if old else round(sum(sum(H[x].values()) for x in days) / nd, 2)
        D["heat"]["SIN"][mi] = [round(100 * sinr / sinh, 2), round(sinr, 2), sinh]
        for g in list(D.get("h95", {})):
            while len(D["h95"][g]) <= mi:
                D["h95"][g].append(None)

    # --- Por región: reservas (corte vs cierre del mes anterior) y aporte diario del mes en curso
    emap = region_map("ListadoEmbalses")
    prev_close = L.replace(day=1) - dt.timedelta(days=1)
    r_now, r_prev = reservas_region(L, emap), reservas_region(prev_close, emap)
    res_reg = {g: [round(100 * r_now[g][0] / r_now[g][1], 2), round(r_now[g][0], 1), round(r_now[g][1], 1),
                   round(100 * r_prev[g][0] / r_prev[g][1], 2), round(r_prev[g][0], 1)] for g in REG if r_now[g][1] and r_prev[g][1]}
    mes_days = [x for x in ap_days if x[:7] == corte_ap[:7]]
    apd_reg = {"days": mes_days}
    for g in REG:
        serie = []
        for x in mes_days:
            a = sum(v for n, v in R[x].items() if rm.get(n) == g)
            h = sum(v for n, v in H.get(x, {}).items() if rm.get(n) == g)
            serie.append(round(100 * a / h, 1) if h else None)
        apd_reg[g] = serie
    apd_reg["SIN"] = [round(100 * sum(R[x].values()) / sum(H[x].values()), 1) for x in mes_days]
    D["reg"] = {"fecha": last, "prev": prev_close.isoformat(), "res": res_reg, "apd": apd_reg}

    def hist_mes(key, x, nat):
        same = [r for r in D[key] if r[0][:7] == x[:7]]
        if same:
            return same[0][2]
        hh = H.get(x, {})
        return round(sum(v for n, v in hh.items() if not (nat and n in DESV_NAT)), 2)

    apd = {r[0]: r for r in D["apd"]}
    apn = {r[0]: r for r in D["apn"]}
    for x in ap_days:
        tot = sum(R[x].values())
        nat = tot - sum(R[x].get(n, 0) for n in DESV_NAT)
        apd[x] = [x, round(tot, 2), apd[x][2] if x in apd else hist_mes("apd", x, False)]
        apn[x] = [x, round(nat, 2), apn[x][2] if x in apn else hist_mes("apn", x, True)]
    D["apd"] = [apd[k] for k in sorted(apd)]
    D["apn"] = [apn[k] for k in sorted(apn)]

    # --- Semanal: agrega semanas completas con escenario disponible
    wk = {r[0]: r for r in D["weekly"]}
    apdd = {r[0]: r[1] for r in D["apd"]}
    for w, (mn, pr, mx) in ESC.items():
        w0 = dt.date.fromisoformat(w)
        dd = [(w0 + dt.timedelta(days=i)).isoformat() for i in range(7)]
        if all(x in apdd for x in dd) and w not in wk:
            wk[w] = [w, round(sum(apdd[x] for x in dd) / 7, 1), mn, pr, mx]
    D["weekly"] = [wk[k] for k in sorted(wk)]
    # escenario de aportes de la senda (promedio de 100 series, GWh/día) por semana
    esc = {r[0]: r[3] for r in D["weekly"]}
    esc.update({w: v[1] for w, v in ESC.items()})
    D["esc"] = dict(sorted(esc.items()))

    # --- Demanda no atendida (DNA): mensual, por subárea y últimos 30 días
    dna_p = daily("DemaNoAtenProg", "Subarea", jan1, hoy)
    dna_n = daily("DemaNoAtenNoProg", "Subarea", jan1, hoy)
    dem = daily("DemaSIN", "Sistema", jan1, hoy)
    mens, sub = {}, {}
    for src, k in ((dna_p, 0), (dna_n, 1)):
        for d, v in src.items():
            mens.setdefault(d[:7], [0.0, 0.0, 0.0])[k] += sum(v.values())
            for n, val in v.items():
                nm = n.replace("SUBAREA ", "").replace("_", "-").title()
                e = sub.setdefault(nm, [0.0, set()])
                e[0] += val
                if val > 0:
                    e[1].add(d)
    for d, v in dem.items():
        mens.setdefault(d[:7], [0.0, 0.0, 0.0])[2] += sum(v.values())
    dlast = max(set(dna_p) | set(dna_n)) if (dna_p or dna_n) else last
    DL = dt.date.fromisoformat(dlast)
    def dna_rango(d0):
        ds = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((DL - d0).days + 1)]
        g_ = sum(sum(dna_p.get(x, {}).values()) + sum(dna_n.get(x, {}).values()) for x in ds)
        m_ = sum(sum(dem.get(x, {}).values()) for x in ds if x in dem)
        return round(g_, 2), round(100 * g_ / m_, 3) if m_ else None
    u30, u30p = dna_rango(DL - dt.timedelta(days=29))
    anio_g = sum(v[0] + v[1] for v in mens.values())
    anio_d = sum(v[2] for v in mens.values())
    # Caribe: consolidado por subárea (los 7 departamentos continentales)
    CARIBE = {"SUBAREA GCM": "GCM", "SUBAREA ATLANTICO": "Atlántico", "SUBAREA BOLIVAR": "Bolívar", "SUBAREA CORDOBA_SUCRE": "Córdoba-Sucre"}
    d30 = (DL - dt.timedelta(days=29)).isoformat()
    car = {v: {"mes": {}, "anio": 0.0, "u30": 0.0, "dias": set()} for v in CARIBE.values()}
    car_dias = set()
    for src in (dna_p, dna_n):
        for d, v in src.items():
            for k, val in v.items():
                if k in CARIBE:
                    e = car[CARIBE[k]]
                    e["mes"][d[:7]] = e["mes"].get(d[:7], 0.0) + val
                    e["anio"] += val
                    if d >= d30:
                        e["u30"] += val
                    if val > 0:
                        e["dias"].add(d); car_dias.add(d)
    meses = sorted(mens)
    caribe = {"meses": meses,
              "sub": {k: {"mes": [round(e["mes"].get(m, 0.0), 3) for m in meses], "anio": round(e["anio"], 2),
                          "u30": round(e["u30"], 2), "dias": len(e["dias"])} for k, e in car.items()},
              "dias_total": len(car_dias)}
    D["dna"] = {"fecha": dlast,
                "mensual": [[m, round(v[0], 2), round(v[1], 2), round(v[2], 0)] for m, v in sorted(mens.items())],
                "sub": [[n, round(v[0], 2), len(v[1])] for n, v in sorted(sub.items(), key=lambda z: -z[1][0])[:10]],
                "u30": [u30, u30p], "anio": [round(anio_g, 2), round(100 * anio_g / anio_d, 3) if anio_d else None], "caribe": caribe}

    try:
        termicas(D, hoy)
    except Exception as e:
        print("Térmicas: no se pudo actualizar:", e, file=sys.stderr)

    g, c = res[last]
    D["meta"].update(fecha=last, E=round(g, 1), cap=round(c, 1), parcial=CA != eom(CA.year, CA.month), dia=CA.day,
                     generado=dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).strftime("%d/%m/%Y %H:%M"),
                     vert_hasta=max(V) if V else D["meta"].get("vert_hasta"))
    out = s[:mt.start(1)] + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + s[mt.end(1):]
    open(dst, "w", encoding="utf-8").write(out)
    print(json.dumps({"corte_reservas": last, "corte_aportes": corte_ap, "reserva_pct": round(100 * g / c, 2),
                      "aportes_mes_sin": D["heat"]["SIN"][CA.month - 1], "cuts_last": D["cuts"][-1]}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

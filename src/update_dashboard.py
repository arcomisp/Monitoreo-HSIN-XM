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

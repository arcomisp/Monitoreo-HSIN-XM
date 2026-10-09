#!/usr/bin/env python3
"""Motor de análisis diario XM – Aportes, Reservas y Vertimientos del SIN.
Uso: python3 xm_brief.py [YYYY-MM-DD]   (fecha de corte; por defecto, último día con datos)
Método: aportes = promedio acumulado del mes (día 1 → corte) vs media histórica del mismo período (GWh/día);
reservas = % de capacidad útil al corte vs cierre del mes anterior (pp y GWh)."""
import json, sys, datetime as dt, urllib.request

API = "https://servapibi.xm.com.co"
REG = ["ANTIOQUIA", "CALDAS", "CARIBE", "CENTRO", "ORIENTE", "VALLE"]

# Senda de Referencia Invierno 2026 (XM, publicada 2026-04-27), % embalse SIN diario desde 2026-05-01
SENDA_INI = "2026-05-01"
SENDA = [62.14, 62.47, 62.79, 62.91, 63.03, 63.14, 63.26, 63.38, 63.5, 63.62, 63.84, 64.06, 64.28, 64.5, 64.71, 64.93, 65.15, 65.46, 65.76, 66.06, 66.37, 66.67, 66.97, 67.27, 67.56, 67.84, 68.12, 68.4, 68.69, 68.97, 69.25, 69.52, 69.79, 70.06, 70.33, 70.6, 70.86, 71.13, 71.39, 71.64, 71.89, 72.15, 72.4, 72.65, 72.9, 73.14, 73.37, 73.6, 73.83, 74.06, 74.29, 74.52, 74.72, 74.92, 75.12, 75.32, 75.52, 75.73, 75.93, 76.18, 76.44, 76.69, 76.95, 77.21, 77.46, 77.72, 77.94, 78.15, 78.37, 78.59, 78.8, 79.02, 79.24, 79.4, 79.57, 79.74, 79.9, 80.07, 80.24, 80.4, 80.55, 80.7, 80.85, 81.0, 81.14, 81.29, 81.44, 81.53, 81.62, 81.71, 81.8, 81.88, 81.97, 82.06, 82.11, 82.17, 82.22, 82.27, 82.32, 82.37, 82.42, 82.43, 82.44, 82.45, 82.46, 82.46, 82.47, 82.48, 82.48, 82.47, 82.47, 82.46, 82.46, 82.45, 82.45, 82.35, 82.25, 82.15, 82.05, 81.94, 81.84, 81.74, 81.6, 81.45, 81.31, 81.17, 81.02, 80.88, 80.74, 80.58, 80.43, 80.28, 80.13, 79.98, 79.82, 79.67, 79.53, 79.38, 79.23, 79.09, 78.94, 78.8, 78.65, 78.59, 78.53, 78.47, 78.41, 78.35, 78.29, 78.23, 78.18, 78.13, 78.09, 78.04, 77.99, 77.94, 77.89, 77.89, 77.88, 77.87, 77.86, 77.86, 77.85, 77.84, 77.87, 77.9, 77.93, 77.95, 77.98, 78.01, 78.04, 78.11, 78.18, 78.25, 78.33, 78.4, 78.47, 78.54, 78.7, 78.86, 79.02, 79.18, 79.34, 79.5, 79.66, 79.82, 79.98, 80.14, 80.31, 80.47, 80.63, 80.8, 80.93, 81.06, 81.19, 81.32, 81.45, 81.58, 81.71, 81.77, 81.84, 81.91, 81.98, 82.05, 82.12, 82.19, 82.26, 82.33, 82.4, 82.47, 82.54, 82.61, 82.69, 82.55]
# Curva de Administración del Riesgo (CAR), % por semana del año
CAR = {"1": 59.83, "2": 58.01, "3": 55.7, "4": 52.91, "5": 50.33, "6": 47.12, "7": 44.6, "8": 42.18, "9": 40.35, "10": 38.48, "11": 36.57, "12": 34.53, "13": 33.57, "14": 32.34, "15": 31.59, "16": 30.62, "17": 30.28, "18": 31.21, "19": 32.16, "20": 33.19, "21": 33.53, "22": 35.49, "23": 37.22, "24": 38.84, "25": 40.1, "26": 42.71, "27": 44.17, "28": 45.69, "29": 47.97, "30": 48.9, "31": 49.58, "32": 49.97, "33": 50.85, "34": 51.34, "35": 51.91, "36": 52.26, "37": 52.67, "38": 52.97, "39": 52.47, "40": 52.38, "41": 51.98, "42": 53.13, "43": 54.21, "44": 55.44, "45": 56.6, "46": 59.23, "47": 61.95, "48": 63.23, "49": 62.87, "50": 62.13, "51": 62.04, "52": 60.86}


def senda(d):
    i = (d - dt.date.fromisoformat(SENDA_INI)).days
    return SENDA[i] if 0 <= i < len(SENDA) else None


def car(d):
    return CAR.get(str(d.isocalendar()[1]))


def post(path, body):
    req = urllib.request.Request(API + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            err = e
    raise err


def daily(metric, entity, d0, d1):
    """Devuelve {fecha: {nombre: valor}}. Parte en bloques de 28 días."""
    out, a = {}, d0
    while a <= d1:
        b = min(a + dt.timedelta(days=27), d1)
        js = post("/daily", {"MetricId": metric, "StartDate": a.isoformat(), "EndDate": b.isoformat(), "Entity": entity})
        for it in js.get("Items", []):
            for e in it["DailyEntities"]:
                if e.get("Value") in (None, ""):
                    continue
                out.setdefault(it["Date"], {})[e.get("Name") or e.get("Id")] = float(e["Value"])
        a = b + dt.timedelta(days=1)
    return out


def region_map(metric):
    js = post("/lists", {"MetricId": metric})
    m = {e["Values"]["Name"]: e["Values"]["HydroRegion"] for it in js["Items"] for e in it["ListEntities"]}
    if metric == "ListadoRios":
        m.setdefault("AMOYA", "CENTRO")  # XM lo reporta en Centro; la API no le asigna región
    return m


def month_aportes(d0, d1, rmap):
    """Aportes acumulados (GWh) real e histórico por región y SIN para [d0, d1]."""
    real, hist = daily("AporEner", "Rio", d0, d1), daily("AporEnerMediHist", "Rio", d0, d1)
    sin_r, sin_h = daily("AporEner", "Sistema", d0, d1), daily("AporEnerMediHist", "Sistema", d0, d1)
    dias = sorted(set(sin_r) & set(sin_h))
    agg = {r: [0.0, 0.0, 0.0, 0.0] for r in REG + ["SIN"]}  # real, hist, real sin desv., hist sin desv.
    for d in dias:
        for k, src in ((0, real), (1, hist)):
            for name, v in src.get(d, {}).items():
                r = rmap.get(name)
                if r in agg:
                    agg[r][k] += v / 1e6
                    if not name.upper().startswith("DESV"):
                        agg[r][k + 2] += v / 1e6
        agg["SIN"][0] += sum(sin_r[d].values()) / 1e6
        agg["SIN"][1] += sum(sin_h[d].values()) / 1e6
    n = len(dias)
    res = {}
    for r, (a, h, a2, h2) in agg.items():
        res[r] = {"real_gwh_dia": a / n if n else None, "hist_gwh_dia": h / n if n else None,
                  "pct": 100 * a / h if h else None}
        if r != "SIN" and abs(h - h2) > 1e-9:  # región con desviaciones: % solo con ríos naturales
            res[r]["pct_sin_desviaciones"] = 100 * a2 / h2 if h2 else None
    return res, dias


def reservas(d0, d1):
    vol, cap = daily("VoluUtilDiarEner", "Sistema", d0, d1), daily("CapaUtilDiarEner", "Sistema", d0, d1)
    s = {}
    for d in sorted(set(vol) & set(cap)):
        v, c = sum(vol[d].values()) / 1e6, sum(cap[d].values()) / 1e6
        s[d] = {"gwh": v, "cap_gwh": c, "pct": 100 * v / c}
    return s


def reservas_region(d, emap):
    day = dt.date.fromisoformat(d)
    vol, cap = daily("VoluUtilDiarEner", "Embalse", day, day).get(d, {}), daily("CapaUtilDiarEner", "Embalse", day, day).get(d, {})
    agg = {r: [0.0, 0.0] for r in REG}
    for name, v in vol.items():
        r = emap.get(name)
        if r in agg and name in cap:
            agg[r][0] += v / 1e6
            agg[r][1] += cap[name] / 1e6
    return {r: {"gwh": a, "cap_gwh": c, "pct": 100 * a / c if c else None} for r, (a, c) in agg.items()}


def run(corte=None):
    hoy = dt.date.today()
    if corte is None:
        # último día con aportes publicados
        probe = daily("AporEner", "Sistema", hoy - dt.timedelta(days=7), hoy)
        corte = dt.date.fromisoformat(max(probe))
    ini = corte.replace(day=1)
    cierre_ant = ini - dt.timedelta(days=1)
    rios, emb = region_map("ListadoRios"), region_map("ListadoEmbalses")

    apor, dias = month_aportes(ini, corte, rios)
    # mes anterior completo, para comparar
    apor_ant, _ = month_aportes(cierre_ant.replace(day=1), cierre_ant, rios)
    # serie diaria SIN del mes (para tendencia de los últimos 7 días)
    sr, sh = daily("AporEner", "Sistema", ini, corte), daily("AporEnerMediHist", "Sistema", ini, corte)
    diario = [{"fecha": d, "gwh": sum(sr[d].values()) / 1e6, "pct": 100 * sum(sr[d].values()) / sum(sh[d].values())}
              for d in sorted(set(sr) & set(sh))]

    res = reservas(cierre_ant - dt.timedelta(days=1), corte)
    ult = max(res)
    r_ult, r_cierre = res[ult], res.get(cierre_ant.isoformat())
    r_ayer = res.get((dt.date.fromisoformat(ult) - dt.timedelta(days=1)).isoformat())
    r7 = res.get((dt.date.fromisoformat(ult) - dt.timedelta(days=7)).isoformat())

    vert = daily("VertEner", "Sistema", ini, corte)
    vert_mes = sum(sum(v.values()) for v in vert.values()) / 1e6

    return {
        "corte_aportes": dias[-1] if dias else None, "dias_mes": len(dias),
        "aportes_mes": apor, "aportes_mes_anterior": apor_ant, "aportes_diarios_sin": diario,
        "reservas": {"fecha": ult, "pct": r_ult["pct"], "gwh": r_ult["gwh"], "cap_gwh": r_ult["cap_gwh"],
                     "cierre_mes_anterior": r_cierre, "ayer": r_ayer, "hace_7_dias": r7,
                     "var_pp_vs_cierre": r_ult["pct"] - r_cierre["pct"] if r_cierre else None,
                     "var_gwh_vs_cierre": r_ult["gwh"] - r_cierre["gwh"] if r_cierre else None,
                     "var_pp_vs_ayer": r_ult["pct"] - r_ayer["pct"] if r_ayer else None,
                     "var_pp_7d": r_ult["pct"] - r7["pct"] if r7 else None,
                     "senda_referencia_pct": senda(dt.date.fromisoformat(ult)),
                     "brecha_vs_senda_pp": r_ult["pct"] - senda(dt.date.fromisoformat(ult)) if senda(dt.date.fromisoformat(ult)) else None,
                     "senda_fin_de_mes_pct": senda((ini.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)),
                     "car_pct": car(dt.date.fromisoformat(ult))},
        "reservas_region": reservas_region(ult, emb),
        "vertimientos_mes_gwh": vert_mes,
        "vertimientos_ultimo_dia_gwh": sum(vert[max(vert)].values()) / 1e6 if vert else 0.0,
    }


if __name__ == "__main__":
    c = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(run(c), indent=1, ensure_ascii=False))

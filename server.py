# server.py
import os
import re
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

# =======================
# Paths e carregamento .env / config.ini
# =======================

ROOT = Path(__file__).resolve().parent
PROJ = ROOT.parent

def _sloppy_env_load(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        os.environ.setdefault(k, v)

def _ini_kv_load(ini_path: Path) -> None:
    if not ini_path.exists():
        return
    for raw in ini_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        os.environ.setdefault(k, v)

for base in (ROOT, PROJ):
    _sloppy_env_load(base / ".env")
    _ini_kv_load(base / "config.ini")

# =======================
# Configs
# =======================

def _resolve_pim_base() -> str:
    base = (
        os.getenv("PIM_BASE_URL")
        or os.getenv("HOST_PIM_MASTER")
        or os.getenv("HOST_PIM_DEV")
        or "http://10.30.73.46:83"
    ).strip()
    if base.endswith("/index.html"):
        base = base[:-len("/index.html")]
    return base.rstrip("/")

PIM_BASE_URL = _resolve_pim_base()
AUTH_PIM = (os.getenv("AUTH_PIM") or "").strip()
DEFAULT_DECIMAIS = int(os.getenv("DECIMAIS", "3"))

EXPORT_TZ_OFFSET = os.getenv("EXPORT_TZ_OFFSET", "-03:00").strip()

def _tz_from_offset(offset_str: str) -> timezone:
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})?", offset_str)
    if not m:
        return timezone.utc
    sign, hh, mm = m.group(1), m.group(2), (m.group(3) or "00")
    delta = timedelta(hours=int(hh), minutes=int(mm))
    if sign == "-":
        delta = -delta
    return timezone(delta)

_EXPORT_TZ = _tz_from_offset(EXPORT_TZ_OFFSET)

def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _fmt_export_dt(ts: datetime) -> str:
    return as_utc(ts).astimezone(_EXPORT_TZ).strftime("%Y-%m-%d %H:%M")

def _filename_for_export(end_dt: datetime) -> str:
    stamp = as_utc(end_dt).astimezone(_EXPORT_TZ).strftime("%Y%m%d%H%M")
    return f"GER_PIM_{stamp}.txt"

# =======================
# Estações (estacoes.ini)
# Formato: principal;retaguarda;divisor;variavel;tag
# =======================

class Estacao:
    def __init__(self, principal: str, retaguarda: str, divisor: float, variavel: str, tag: str):
        self.principal = principal
        self.retaguarda = retaguarda
        self.divisor = float(divisor or 1.0)
        self.variavel = (variavel or "").strip()
        self.tag = tag.strip()

def _load_estacoes() -> List[Estacao]:
    for p in (ROOT / "estacoes.ini", PROJ / "estacoes.ini"):
        if p.exists():
            out: List[Estacao] = []
            for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                parts = [x.strip() for x in line.split(";")]
                if len(parts) < 5:
                    continue
                principal, retaguarda, divisor, variavel, tag = parts[:5]
                try:
                    out.append(Estacao(principal, retaguarda, float(divisor), variavel, tag))
                except Exception:
                    continue
            return out
    return []

ESTACOES: List[Estacao] = _load_estacoes()

# =======================
# App
# =======================

app = FastAPI(title="PIM Gateway", version="2.0.0")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    # Timeout default + específicos (evita ValueError)
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0, read=10.0, write=10.0))

@app.on_event("shutdown")
async def _shutdown():
    http: httpx.AsyncClient = app.state.http
    if http:
        await http.aclose()

def _pim_headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if AUTH_PIM:
        h["PIM-Auth"] = AUTH_PIM
    return h

async def _pim_get(path: str, params: Dict[str, Any] | None = None) -> httpx.Response:
    if not PIM_BASE_URL:
        raise HTTPException(status_code=500, detail="PIM_BASE_URL não configurada")
    url = f"{PIM_BASE_URL}{path}"
    http: httpx.AsyncClient = app.state.http
    return await http.get(url, params=params, headers=_pim_headers())

# =======================
# Util: extrair séries
# =======================

def _extract_series(payload: Any) -> List[Dict[str, Any]]:
    def norm_time(x: Any) -> Optional[datetime]:
        if isinstance(x, str):
            try:
                return as_utc(datetime.fromisoformat(x.replace("Z", "+00:00")))
            except Exception:
                return None
        return None
    def norm_val(v: Any) -> Optional[float]:
        try:
            return float(v)
        except Exception:
            return None

    seq: List[Any]
    if isinstance(payload, dict):
        seq = payload.get("items") or payload.get("data") or payload.get("values") or payload.get("leituras") or []
    elif isinstance(payload, list):
        seq = payload
    else:
        seq = []

    out: List[Dict[str, Any]] = []
    for it in seq:
        if not isinstance(it, dict):
            continue
        t = (
            it.get("timestamp") or it.get("dataHora") or it.get("data") or
            it.get("hora") or it.get("instante")
        )
        v = it.get("valor") or it.get("value") or it.get("medicao") or it.get("leitura")
        dt = norm_time(t)
        fv = norm_val(v)
        if dt is not None and fv is not None:
            out.append({"timestamp": dt, "value": fv})
    return out

# =======================
# Coleta PIM (com variavel)
# =======================

_PARAM_NAMES = [
    ("datainicio", "datafim"),
    ("dataInicio", "dataFim"),
    ("inicio", "fim"),
    ("start", "end"),
    ("startDate", "endDate"),
]

async def _pim_fetch_values(
    ponto_id: int,
    start: datetime,
    end: datetime,
    limit: int = 10000,
    variavel: Optional[str] = None,
) -> List[Dict[str, Any]]:
    start_iso = as_utc(start).isoformat().replace("+00:00", "Z")
    end_iso = as_utc(end).isoformat().replace("+00:00", "Z")

    attempts: List[Tuple[str, Dict[str, Any]]] = []

    # 1) Com variavel no path (primeira prioridade)
    if variavel:
        base_paths = [
            f"/api/v3/pontos/{ponto_id}/variaveis/{variavel}/valores",
            f"/api/v3/pontos/{ponto_id}/variaveis/{variavel}/leituras",
        ]
        for p in base_paths:
            for a, b in _PARAM_NAMES:
                attempts.append((p, {a: start_iso, b: end_iso, "take": limit}))

    # 2) Por ponto, sem variavel
    base_paths2 = [
        f"/api/v3/pontos/{ponto_id}/valores",
        f"/api/v3/pontos/{ponto_id}/leituras",
    ]
    for p in base_paths2:
        for a, b in _PARAM_NAMES:
            attempts.append((p, {a: start_iso, b: end_iso, "take": limit}))

    # 3) Endpoints globais
    base_paths3 = [
        "/api/v3/valores",
        "/api/v3/leituras",
        "/api/v3/values",
    ]
    for p in base_paths3:
        for a, b in _PARAM_NAMES:
            attempts.append((p, {"pontoid": ponto_id, a: start_iso, b: end_iso, "take": limit}))

    last_err = None
    for path, params in attempts:
        try:
            r = await _pim_get(path, params)
            if r.status_code != 200:
                last_err = f"{path} -> {r.status_code}"
                continue
            series = _extract_series(r.json())
            if series:
                series.sort(key=lambda x: x["timestamp"])
                return series
        except Exception as e:
            last_err = f"{path} -> {e}"

    logging.warning("Sem dados para ponto %s (variavel=%s). Último erro: %s", ponto_id, variavel, last_err)
    return []

# =======================
# Rotas
# =======================

@app.get("/")
async def root():
    return {"status": "ok", "docs": "/docs", "api": "/api", "pim_base": PIM_BASE_URL}

@api.get("/debug/pim-check")
async def pim_check():
    try:
        r = await _pim_get("/api/v3/pontos", {"take": 1})
        snippet = r.text[:200].replace("\r", "").replace("\n", "\\n")
        return {
            "PIM_BASE_URL": PIM_BASE_URL,
            "AUTH_PIM_is_set": bool(AUTH_PIM),
            "test_url": f"{PIM_BASE_URL}/api/v3/pontos",
            "status_code": r.status_code,
            "content_type": r.headers.get("Content-Type"),
            "snippet": snippet if r.status_code == 200 else r.text,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api.get("/health")
async def health():
    checks: Dict[str, Any] = {}
    try:
        r = await _pim_get("/api/v3/pontos", {"take": 1})
        checks["pim"] = "ok" if r.status_code == 200 else f"erro, status {r.status_code}"
    except Exception as e:
        checks["pim"] = f"erro, {e}"
    status = "ok" if checks.get("pim") == "ok" else "degraded"
    return {"status": status, "checks": checks}

# Proxy dos pontos
@api.get("/pontos")
async def listar_pontos(
    pontoid: Optional[int] = Query(None),
    tipocoletacceeid: Optional[int] = Query(None),
    nome: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    pasta: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    ultimacoleta_datainicio: Optional[str] = Query(None, alias="ultimacoleta-datainicio"),
    ultimacoleta_datafim: Optional[str] = Query(None, alias="ultimacoleta-datafim"),
    ultimacoleta_temporelativo: Optional[str] = Query(None, alias="ultimacoleta-temporelativo"),
    ultimacoleta_hasvalue: Optional[bool] = Query(None, alias="ultimacoleta-hasvalue"),
    skip: Optional[int] = Query(None),
    take: Optional[int] = Query(None),
    sortingproperty: Optional[str] = Query(None),
    sorting: Optional[str] = Query(None),
):
    params: Dict[str, Any] = {}
    def put(k, v):
        if v is not None:
            params[k] = v
    for k, v in [
        ("pontoid", pontoid),
        ("tipocoletacceeid", tipocoletacceeid),
        ("nome", nome),
        ("tipo", tipo),
        ("pasta", pasta),
        ("path", path),
        ("ultimacoleta-datainicio", ultimacoleta_datainicio),
        ("ultimacoleta-datafim", ultimacoleta_datafim),
        ("ultimacoleta-temporelativo", ultimacoleta_temporelativo),
        ("ultimacoleta-hasvalue", ultimacoleta_hasvalue),
        ("skip", skip),
        ("take", take),
        ("sortingproperty", sortingproperty),
        ("sorting", sorting),
    ]:
        put(k, v)

    r = await _pim_get("/api/v3/pontos", params)
    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="PIM não autorizado, verifique AUTH_PIM")
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return JSONResponse(content=r.json())

# Proxy dos medidores
@api.get("/pim/medidores")
async def pim_medidores(
    numerodeserie: Optional[str] = Query(None),
    pasta: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    take: Optional[int] = Query(None),
    sortingproperty: Optional[str] = Query(None),
    sorting: Optional[str] = Query(None),
):
    params: Dict[str, Any] = {}
    for k, v in [
        ("numerodeserie", numerodeserie),
        ("pasta", pasta),
        ("path", path),
        ("skip", skip),
        ("take", take),
        ("sortingproperty", sortingproperty),
        ("sorting", sorting),
    ]:
        if v is not None:
            params[k] = v
    r = await _pim_get("/api/v3/medidores", params)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return JSONResponse(content=r.json())

# Série crua (com variavel opcional)
@api.get("/pim/valores")
async def pim_valores(
    ponto_id: int = Query(...),
    start_datetime: datetime = Query(...),
    end_datetime: datetime = Query(...),
    limit: int = Query(10000),
    variavel: Optional[str] = Query(None, description="Nome exato da variável no PIM (ex.: EneatDel)"),
):
    if end_datetime <= start_datetime:
        raise HTTPException(status_code=400, detail="end_datetime deve ser maior que start_datetime")
    series = await _pim_fetch_values(ponto_id, start_datetime, end_datetime, limit=limit, variavel=variavel)
    out = [{"timestamp": as_utc(x["timestamp"]).isoformat().replace("+00:00", "Z"), "value": x["value"]} for x in series]
    return out

# Debug: tenta vários endpoints e retorna status/samples
@api.get("/pim/probe")
async def pim_probe(
    ponto_id: int = Query(...),
    start_datetime: datetime = Query(...),
    end_datetime: datetime = Query(...),
    variavel: Optional[str] = Query(None),
):
    start_iso = as_utc(start_datetime).isoformat().replace("+00:00", "Z")
    end_iso = as_utc(end_datetime).isoformat().replace("+00:00", "Z")
    attempts: List[Tuple[str, Dict[str, Any]]] = []

    if variavel:
        for p in (f"/api/v3/pontos/{ponto_id}/variaveis/{variavel}/valores",
                  f"/api/v3/pontos/{ponto_id}/variaveis/{variavel}/leituras"):
            for a, b in _PARAM_NAMES:
                attempts.append((p, {a: start_iso, b: end_iso, "take": 2000}))

    for p in (f"/api/v3/pontos/{ponto_id}/valores", f"/api/v3/pontos/{ponto_id}/leituras"):
        for a, b in _PARAM_NAMES:
            attempts.append((p, {a: start_iso, b: end_iso, "take": 2000}))

    results = []
    for path, params in attempts:
        try:
            r = await _pim_get(path, params)
            samples = 0
            if r.status_code == 200:
                samples = len(_extract_series(r.json()))
            results.append({"url": f"{PIM_BASE_URL}{path}", "params": params, "status": r.status_code, "samples": samples})
        except Exception as e:
            results.append({"url": f"{PIM_BASE_URL}{path}", "params": params, "status": None, "error": str(e)})
    return results

# Exporta arquivo GER_PIM_YYYYMMDDHHmm.txt
@api.get("/pim/export-ger")
async def export_ger_pim(
    start_datetime: datetime = Query(..., description="ISO8601, ex: 2025-08-25T15:10:00Z"),
    end_datetime: datetime = Query(..., description="ISO8601, ex: 2025-08-25T18:05:00Z"),
    tags: Optional[List[str]] = Query(None, description="Filtrar por tags do estacoes.ini; repita o parâmetro"),
    decimais: Optional[int] = Query(None, description="Override das casas decimais"),
    fallback_retaguarda: bool = Query(True, description="Se principal sem dados, tenta retaguarda"),
    usar_nome_medidor_de_saida: str = Query("principal", pattern="^(principal|origem)$"),
    limit_por_ponto: int = Query(100000),
):
    if end_datetime <= start_datetime:
        raise HTTPException(status_code=400, detail="end_datetime deve ser maior que start_datetime")
    casas = DEFAULT_DECIMAIS if decimais is None else int(decimais)

    # Seleção por tags (coluna 5 do estacoes.ini)
    lista = ESTACOES
    if tags:
        wanted = set(tags)
        lista = [e for e in ESTACOES if e.tag in wanted]
        if not lista:
            raise HTTPException(status_code=404, detail="Nenhuma estação de estacoes.ini casa com 'tags' passados")

    # Helpers: resolver pontoId pelo nome do medidor (principal/retaguarda)
    async def _resolver_pontoid(chave: str) -> Optional[int]:
        # tenta por nome:
        try:
            r = await _pim_get("/api/v3/pontos", {"nome": chave, "take": 1})
            if r.status_code == 200:
                items = (r.json() or {}).get("items") or []
                if items:
                    return int(items[0].get("pontoId"))
        except Exception:
            pass
        # tenta por path:
        try:
            r = await _pim_get("/api/v3/pontos", {"path": chave, "take": 1})
            if r.status_code == 200:
                items = (r.json() or {}).get("items") or []
                if items:
                    return int(items[0].get("pontoId"))
        except Exception:
            pass
        return None

    buf = io.StringIO()

    for est in lista:
        origem = "principal"
        var = est.variavel or None

        pid = await _resolver_pontoid(est.principal)
        serie: List[Dict[str, Any]] = []
        if pid:
            serie = await _pim_fetch_values(pid, start_datetime, end_datetime, limit=limit_por_ponto, variavel=var)

        if not serie and fallback_retaguarda and est.retaguarda:
            pid2 = await _resolver_pontoid(est.retaguarda)
            if pid2:
                s2 = await _pim_fetch_values(pid2, start_datetime, end_datetime, limit=limit_por_ponto, variavel=var)
                if s2:
                    serie = s2
                    origem = "retaguarda"

        if not serie:
            continue

        serie.sort(key=lambda x: x["timestamp"])
        col1 = est.principal if usar_nome_medidor_de_saida == "principal" else (est.principal if origem == "principal" else est.retaguarda)
        div = est.divisor or 1.0

        for it in serie:
            valor = round(float(it["value"]) / div, casas)
            dt_str = _fmt_export_dt(it["timestamp"])
            buf.write(f"{col1};{est.tag};{dt_str};{valor:.{casas}f}\n")

    payload = buf.getvalue()
    buf.close()

    file_path = ROOT / _filename_for_export(end_datetime)
    file_path.write_text(payload, encoding="utf-8")
    return {"message": "Arquivo salvo com sucesso", "file_path": str(file_path)}

# Inclui router
app.include_router(api)

# Logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=True)

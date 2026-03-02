# CASTOR ELECCIONES (solo-front)

Esta rama (`solo-front`) deja el proyecto en perfil **front-only** para renderizar el dashboard sin módulos de LLM/scraping/chat/agent/review.

## Modo solo-front

- `FRONT_ONLY_MODE=true` (por defecto en esta rama)
- Login obligatorio con `cédula + código` (`ELECTORAL_ACCESS_USERS`) para acceder a vistas y APIs
- Blueprints activos: `web`, `health`, `campaign-team`, `e14-data`, `geography`, `incidents`
- Se removió del template: chat RAG y acción de subir actas (OCR upload)
- Flujo principal: recibir lista de `document_id` y sincronizar resultados desde Azure OCR (`/api/e14-data/documents/sync`)
- Webhook para app #2 (completed): `POST /api/e14-data/webhook/completed` con `X-Webhook-Token`
- Incidentes en `solo-front`: almacenamiento en memoria (sin SQLite)

---

**Plataforma de Inteligencia Electoral** — Extracción y auditoría de actas E-14, War Room de incidentes y agente autónomo de anomalías.

---

## Stack

| Componente | Tecnología |
|---|---|
| **Backend** | Python 3.10+ / Flask 3.0 — monolito en :5001 |
| **Frontend** | Jinja2 + Vanilla JS + Chart.js + Leaflet.js |
| **OCR E-14** | Azure custom Web App + LLM auditor (primario) |
| **LLM** | OpenAI GPT-4o · Anthropic Claude sonnet-4/opus-4 · Ollama (local) |
| **RAG** | ChromaDB + OpenAI `text-embedding-3-small` |
| **Scraping** | httpx async · 2Captcha (CAPTCHA bypass client-side) |
| **Auth** | JWT (Flask-JWT-Extended) |
| **Store** | In-memory (TTL 5 min, SHA-256 dedup) — sin DB requerida |

---

## Módulos Activos

| Módulo | Rutas |
|---|---|
| **E-14 OCR** — scraper + Azure OCR + store en memoria | `e14_data.py`, `scraper.py` |
| **War Room** — incidentes, KPIs, mapa choropleth | `incidents.py`, `geography.py`, `campaign_team.py` |
| **Chat RAG E-14** — consultas en lenguaje natural sobre actas | `chat.py` |
| **HITL Review** — revisión y corrección humana de actas | `review.py` |
| **Agente Autónomo** — anomalías, alertas, briefings, escalación | `agent.py` |

---

## Pipeline E-14

```
Portal Registraduría
  ├─ GET /auth/csrf          → JWT (válido 24h)
  ├─ POST /consultarE14      → tokens de mesa (CAPTCHA vacío — client-side only)
  └─ POST /descargae14       → PDF

data/e14/raw/flat/*.pdf
  └─ POST /api/e14-data/azure/process
       └─ azure_ocr_service.py → Azure Web App OCR + LLM auditor
            └─ {stem}_azure.json  (campos *_adjusted + *_original)

data/e14/processed/tesseract_results/  (430+ *_azure.json)
  └─ E14JsonStore (in-memory, TTL 5 min)
       └─ GET /api/e14-data/* → Dashboard · Agent · RAG
```

---

## API Routes (12 activas)

| Blueprint | Prefix | Propósito |
|---|---|---|
| `electoral_auth_bp` | `/` | Login electoral E-14 |
| `web_bp` | `/` | Páginas web |
| `auth_bp` | `/api` | Autenticación JWT |
| `health_bp` | `/api` | Health check |
| `chat_bp` | `/api` | Chat RAG E-14 |
| `review_bp` | `/api/electoral/review` | HITL review |
| `e14_data_bp` | `/api/e14-data` | Datos E-14 + Azure batch |
| `scraper_bp` | `/api/scraper` | Control scraper + OCR batch |
| `agent_bp` | `/api/agent` | Electoral Intelligence Agent |
| `incidents_bp` | `/api/incidents` | War Room — incidentes |
| `campaign_team_bp` | `/api/campaign-team` | War Room — dashboard |
| `geography_bp` | `/api/geography` | Mapa choropleth, GeoJSON |

---

## Inicio Rápido

```bash
cd backend
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
export ELECTORAL_ACCESS_USERS='[{"cedula":"1234567890","code":"ABCD-EFGH-IJKL-MNOP","name":"Usuario Demo","email":"demo@local"}]'
export OCR_WEBHOOK_TOKEN='change-this-webhook-token'
FRONT_ONLY_MODE=true python run.py   # login: http://localhost:5001/electoral/login
```

Nota:
- `backend/requirements.txt` = perfil ligero `solo-front`.
- `backend/requirements.full.txt` = stack completo histórico.

### Variables de entorno clave

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
AZURE_OCR_URL=https://castor-ocr-hpcxdsbmeqgvdebd.centralus-01.azurewebsites.net
AZURE_OCR_API_KEY=...
CAPTCHA_2_API_KEY=...
# Opcionales — el sistema corre sin ellas:
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
```

---

## Modelos de IA

| Variable | Modelo | Uso |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o` | RAG, reportes |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embeddings RAG |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Agente, análisis |
| `AZURE_OCR_URL` | `castor-ocr-hpcxdsbmeqgvdebd…` | OCR batch primario |

---

## Testing

```bash
cd backend
pytest tests/
pytest --cov=. tests/
```

---

## Documentación E-14

| Documento | Descripción |
|---|---|
| [`docs/e14/e14-scraper-tecnico.md`](docs/e14/e14-scraper-tecnico.md) | Pipeline completo: JWT → CAPTCHA bypass → descarga → Azure OCR, schema JSON |
| [`docs/e14/e14-data-access-strategies.md`](docs/e14/e14-data-access-strategies.md) | 6 estrategias de acceso (E0–E5) con benchmark y árbol de decisión |
| [`docs/e14/e14-benchmark-resultados.md`](docs/e14/e14-benchmark-resultados.md) | Tiempos reales: 1 / 10 / 100 / 1k / 100k actas |
| [`docs/e14/E14_API_ENDPOINTS.md`](docs/e14/E14_API_ENDPOINTS.md) | Referencia completa de endpoints activos |

---

## Licencia

Proyecto privado — Todos los derechos reservados

**Autor**: Carlos Ariel Sánchez Torres — Clio Circle AI

---

*CASTOR ELECCIONES — Inteligencia Electoral en Tiempo Real*

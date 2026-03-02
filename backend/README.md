# CASTOR ELECCIONES - Backend Microservice

## Descripción
Microservicio de análisis electoral en tiempo real usando Twitter/X, procesamiento de lenguaje natural y RAG (Retrieval Augmented Generation).

## Características Principales

### 1. Análisis de Twitter
- Búsqueda de tweets por candidato/tema
- Análisis de sentimiento (positivo/negativo/neutral)
- Clasificación por ejes del Plan Nacional de Desarrollo (PND)
- Rate limiting inteligente (500/día, 15K/mes)

### 2. Métricas Electorales
- **ICCE**: Índice Compuesto de Capacidad Electoral (0-100)
- **SOV**: Share of Voice - % de conversación
- **SNA**: Sentimiento Neto Agregado (-100 a +100)
- **Momentum**: Velocidad de cambio en la conversación

### 3. Chat RAG Inteligente
- Indexación automática de tweets y análisis
- Búsqueda semántica con embeddings de OpenAI
- Respuestas contextuales con GPT-4o
- Historial de conversaciones

### 4. Dashboard en Tiempo Real
- Visualización de métricas por eje PND
- Mapa de Colombia con distribución geográfica
- Histórico de análisis
- Timer de reset de API

## Arquitectura

```
backend/
├── app/
│   ├── __init__.py          # Factory de la aplicación Flask
│   ├── constants.py          # Constantes y configuración
│   ├── routes/               # Endpoints de la API
│   │   ├── media.py          # Análisis de medios
│   │   ├── chat.py           # Chat y RAG
│   │   ├── health.py         # Health checks
│   │   ├── forecast.py       # Predicciones
│   │   └── campaign.py       # Estrategias
│   ├── schemas/              # Modelos Pydantic
│   ├── services/             # Lógica de negocio
│   ├── strategies/           # Strategy pattern para temas PND
│   └── interfaces/           # Interfaces abstractas
├── services/
│   ├── twitter_service.py    # Cliente de Twitter API
│   ├── sentiment_service.py  # Análisis de sentimiento
│   ├── openai_service.py     # Integración OpenAI
│   ├── rag_service.py        # RAG y embeddings
│   └── database_service.py   # Persistencia SQLite
├── models/
│   └── database.py           # Modelos SQLAlchemy
├── utils/
│   ├── cache.py              # Sistema de caché
│   ├── circuit_breaker.py    # Patrón circuit breaker
│   └── twitter_rate_tracker.py
├── data/
│   ├── castor.db             # Base de datos principal
│   └── rag_store.sqlite3     # Vector store RAG
├── config.py                 # Configuración
├── main.py                   # Entry point
└── requirements.txt          # Dependencias
```

## Instalación

### Requisitos
- Python 3.9+
- SQLite3
- Claves de API:
  - Twitter Bearer Token
  - OpenAI API Key

### Setup

```bash
# Clonar repositorio
git clone <repo-url>
cd castor/backend

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias (perfil ligero solo-front)
pip install -r requirements.txt
# Si necesitas el stack histórico completo:
# pip install -r requirements.full.txt

# Ejecutar
FRONT_ONLY_MODE=true python run.py
```

### Docker

```bash
# Construir imagen
docker build -t castor-elecciones .

# Ejecutar
docker run -p 5001:5001 \
  -e TWITTER_BEARER_TOKEN="..." \
  -e OPENAI_API_KEY="..." \
  castor-elecciones
```

## API Endpoints

### Health & Status
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/twitter-usage` | Uso de API Twitter |

### Análisis de Medios
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/media/analyze` | Ejecutar análisis |
| GET | `/api/media/history` | Histórico de análisis |
| GET | `/api/media/analysis/{id}` | Detalle de análisis |
| GET | `/api/media/tweets/{id}` | Tweets de un análisis |

### Chat RAG
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/chat/rag` | Preguntar al RAG |
| GET | `/api/chat/rag/stats` | Estadísticas del RAG |
| POST | `/api/chat/rag/search` | Búsqueda semántica |
| POST | `/api/chat/rag/sync-latest` | Sincronizar con BD |

### Forecast
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/forecast/predict` | Predicción electoral |

## Variables de Entorno

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `TWITTER_BEARER_TOKEN` | Sí | Token de Twitter API |
| `OPENAI_API_KEY` | Sí | Clave de OpenAI |
| `SECRET_KEY` | Sí | Clave secreta Flask |
| `FLASK_ENV` | No | development/production |
| `DATABASE_URL` | No | URL de base de datos |
| `TWITTER_DAILY_TWEET_LIMIT` | No | Límite diario (default: 500) |
| `TWITTER_MONTHLY_LIMIT` | No | Límite mensual (default: 15000) |

## Base de Datos

### Tablas Principales
- `api_calls`: Registro de llamadas a la API
- `tweets`: Tweets recolectados
- `analysis_snapshots`: Resúmenes de análisis
- `pnd_axis_metrics`: Métricas por eje PND
- `users`: Usuarios del sistema

### RAG Store
- Embeddings vectoriales con OpenAI text-embedding-3-small
- Documentos indexados: tweets, snapshots, métricas PND
- Búsqueda por similitud coseno

## Patrones de Diseño

1. **Strategy Pattern**: Clasificación de temas PND
2. **Factory Pattern**: Creación de servicios
3. **Repository Pattern**: Acceso a datos
4. **Circuit Breaker**: Resilencia en APIs externas
5. **Singleton**: Servicios compartidos (RAG, DB)

## Licencia
Propietario - CASTOR ELECCIONES

## Contacto
- Email: arielsanroj@gmail.com

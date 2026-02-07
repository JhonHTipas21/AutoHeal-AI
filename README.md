# AutoHeal AI 🛡️

> **Autonomous AIOps Self-Healing Infrastructure Platform**

An enterprise-grade autonomous infrastructure healing system that monitors, analyzes, and automatically remediates incidents using AI-driven decision making.

![Dashboard](docs/images/dashboard.png)

## 🚀 Features

- **Real-time Monitoring** - Prometheus metrics collection with anomaly detection
- **Log Intelligence** - AI-powered log analysis with SLM (Small Language Model)
- **Incident Management** - Automated incident correlation and lifecycle management
- **OODA-based Healing** - Observe → Orient → Decide → Act autonomous loop
- **Kubernetes Actions** - Pod restart, scaling, rollback with safety controls
- **Audit Trail** - Complete reasoning traces and action logging
- **Command Center Dashboard** - Professional NOC-style interface

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Prometheus    │    │      Loki       │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   Monitoring    │    │ Log Intelligence│
│    :8000        │    │     :8001       │
└────────┬────────┘    └────────┬────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
         ┌─────────────────┐
         │Incident Manager │
         │     :8002       │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ AutoHeal Agent  │◄──────┐
         │     :8003       │       │
         └────────┬────────┘       │
                  │                │
         ┌────────┴────────┐       │
         ▼                 ▼       │
┌─────────────────┐ ┌─────────────────┐
│  K8s Executor   │ │ Audit Service   │
│     :8004       │ │     :8005       │
└─────────────────┘ └─────────────────┘
```

## 📦 Services

| Service | Port | Description |
|---------|------|-------------|
| Monitoring | 8000 | Prometheus metrics & anomaly detection |
| Log Intelligence | 8001 | AI log analysis & commit correlation |
| Incident Manager | 8002 | Event correlation & lifecycle management |
| AutoHeal Agent | 8003 | OODA reasoning & healing orchestration |
| K8s Executor | 8004 | Kubernetes action execution |
| Audit Service | 8005 | Decision logging & compliance |
| Dashboard | 8501 | Streamlit Command Center UI |

## 🛠️ Quick Start

### Prerequisites
- Python 3.9+
- Docker & Docker Compose (optional)

### Run with Python (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Start backend services
cd services/audit-service && PYTHONPATH=../.. python3 -m uvicorn src.main:app --port 8005 &
cd services/incident-manager && PYTHONPATH=../.. python3 -m uvicorn src.main:app --port 8002 &
cd services/autoheal-agent && PYTHONPATH=../.. python3 -m uvicorn src.main:app --port 8003 &
cd services/k8s-executor && PYTHONPATH=../.. python3 -m uvicorn src.main:app --port 8004 &

# Start Dashboard
cd dashboard && python3 -m streamlit run app.py --server.port 8501
```

### Run with Docker

```bash
docker-compose up -d
```

### Access

- **Dashboard**: http://localhost:8501
- **API Docs**: http://localhost:8002/docs

## 📊 Dashboard

The Command Center dashboard provides:

- **KPI Cards** - Total incidents, MTTR, auto-remediation rate
- **Real-time Latency Chart** - Visualize spikes and recoveries
- **Live Incident Feed** - Severity-colored event stream
- **AI Reasoning Terminal** - OODA loop decision trace
- **Quick Actions** - Manual override controls

## 🔄 OODA Healing Loop

1. **Observe** - Collect metrics and incident data
2. **Orient** - Analyze root cause with pattern matching
3. **Decide** - Generate healing plan with confidence score
4. **Act** - Execute actions via K8s Executor

## 🧪 Test the System

```bash
# Create a test incident
curl -X POST http://localhost:8002/api/v1/events/anomaly \
  -H "Content-Type: application/json" \
  -d '{"event_id": "test-001", "anomaly_type": "error_rate_spike", 
       "severity": "high", "target_service": "demo-service"}'

# View incidents
curl http://localhost:8002/api/v1/incidents

# Trigger healing
curl -X POST http://localhost:8003/api/v1/heal \
  -H "Content-Type: application/json" \
  -d '{"incident_id": "<incident_id>", "target_service": "demo-service"}'
```

## 📁 Project Structure

```
AutoHeal-AI/
├── services/
│   ├── monitoring/        # Prometheus integration
│   ├── log-intelligence/  # SLM log analysis
│   ├── incident-manager/  # Event correlation
│   ├── autoheal-agent/    # OODA healing engine
│   ├── k8s-executor/      # K8s actions
│   └── audit-service/     # Decision logging
├── dashboard/             # Streamlit UI
├── shared/                # Common utilities
├── infrastructure/        # Prometheus, Grafana, Loki configs
└── docker-compose.yml
```

## 🎯 Tech Stack

- **Backend**: Python 3.11, FastAPI, Pydantic
- **Frontend**: Streamlit, Plotly
- **Orchestration**: Docker, Kubernetes
- **Monitoring**: Prometheus, Grafana, Loki
- **AI**: SLM (Small Language Model) for analysis

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

---

**Built with ❤️ by Jhon Harvey Tipas**

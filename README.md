<div align="center">

# 🌫️ AirPulse — Real-Time Air Quality Monitor

**A full-stack AQI dashboard with live data, ML prediction, and AI health guidance.**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![WAQI](https://img.shields.io/badge/WAQI-Live%20AQI-00B4D8?style=for-the-badge)](https://waqi.info)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

### 🔗 [**Live Dashboard**](https://airpulse-minor-project.onrender.com/) · [**API Docs**](#-api-reference) · [**Architecture**](#-architecture) · [**Contributing**](#-contributing)

</div>

---

## 🚀 **Live Demo**

**Explore the live application here:** [![Live Dashboard](https://img.shields.io/badge/Live%20Dashboard-airpulse.onrender.com-00B4D8?style=flat-square)](https://airpulse-minor-project.onrender.com/)

The dashboard is hosted on Render and provides real-time air quality data for 150+ cities worldwide.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🗺️ **Live AQI Map** | Interactive Leaflet map with real-time station markers across the globe |
| 🤖 **Guidance Bot** | Chat-style AI guidance with asthma-safe follow-ups based on current AQI |
| 📊 **ML Prediction** | Random Forest model predicts AQI from pollutant levels |
| 🌡️ **24h Heatmap** | Hour × Day heatmap showing actual hourly pollution patterns |
| 🔍 **Smart Search** | City/station search with alias resolution (uk→united-kingdom, etc.) |
| 📍 **Geolocation** | "Locate Me" finds the nearest air quality station to your coordinates |
| 📈 **Analytics** | Historical trends, ranking tables, pollutant donut charts |
| 🎬 **Cinematic Hero** | Parallax city backgrounds that shift with time of day (day/evening/night) |
| 🌐 **150+ Cities** | Pre-monitored cities including Delhi, Beijing, London, New York, Tokyo |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (UI Layer)                                          │
│  templates/*.html  ·  static/css/  ·  static/js/            │
│  Chart.js · Leaflet.js · Vanilla CSS animations             │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Flask API Layer  (app.py → backend/)                        │
│  ┌─────────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │  routes/    │  │ routes/  │  │  routes/             │   │
│  │  api.py     │  │  ml.py   │  │  views.py            │   │
│  │  /api/*     │  │ /predict │  │  / /analytics        │   │
│  │  /heatmap   │  │ /advice  │  │  /predict            │   │
│  └──────┬──────┘  └────┬─────┘  └──────────────────────┘   │
│         └──────────────┘                                     │
│                  │ calls                                     │
│         ┌────────▼────────────────┐                         │
│         │  services/              │                         │
│         │  waqi.py   ml.py        │                         │
│         │  core_live.py           │                         │
│         └────────┬────────────────┘                         │
└──────────────────┼──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
   ┌────▼────┐          ┌─────▼──────┐
   │  WAQI   │          │  models/   │
   │  API    │          │  *.pkl     │
   │  Live   │          │  data/     │
   │  Data   │          │  *.csv     │
   └─────────┘          └────────────┘
```

---

## 📁 Project Structure

```
air-quality-monitor/
│
├── app.py                    # App entry shim (delegates to backend/)
├── run.py                    # 🚀 Main server entry point
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── .gitignore
├── README.md
│
├── backend/                  # Modular Flask application
│   └── app/
│       ├── __init__.py       # Flask factory (create_app)
│       ├── config.py         # All configuration & constants
│       ├── utils.py          # Shared helper functions
│       ├── routes/
│       │   ├── api.py        # REST API endpoints
│       │   ├── ml.py         # ML prediction + Guidance Bot
│       │   └── views.py      # HTML page routes
│       └── services/
│           ├── waqi.py       # WAQI API proxy & caching
│           ├── ml.py         # Model loading (pkl files)
│           ├── openai_guidance.py # OpenAI-backed guidance helper
│           └── core_live.py  # Live history management
│
├── models/                   # ML model artifacts
│   ├── aqi_model_random_forest.pkl
│   ├── aqi_scaler.pkl
│   ├── aqi_encoders.pkl
│   └── notebooks/
│       └── model_training.ipynb
│
├── data/                     # Dataset
│   └── globalAirQuality.csv
│
├── templates/                # Jinja2 HTML templates
│   ├── index.html            # Main dashboard
│   ├── analytics.html        # City trends & statistics
│   └── predict.html          # AQI prediction form
│
└── static/
    ├── css/style.css          # All styles + Guidance Bot modal CSS
    ├── js/
    │   ├── main.js            # Dashboard logic + Guidance Bot
    │   ├── analytics.js       # Analytics page charts
    │   └── predict.js         # Prediction form logic
    └── assets/hero/           # City background images
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Anant-Goel2006/Real-Time-Air-Quality-Monitoring-System-with-ML-Prediction-Minor-Project-.git
cd Real-Time-Air-Quality-Monitoring-System-with-ML-Prediction-Minor-Project-
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and set your WAQI_API_TOKEN and OPENAI_API_KEY
# Get a free token at: https://aqicn.org/data-platform/token/
```

### 3. Run

```bash
python run.py
```

Open in browser:
| Page | URL |
|------|-----|
| 🏠 Dashboard | http://127.0.0.1:8080/ |
| 📊 Analytics | http://127.0.0.1:8080/analytics |
| 🤖 Prediction | http://127.0.0.1:8080/predict |

---

## 🔌 API Reference

### Live AQI

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/live/<city>` | Live AQI for a city or station |
| `GET` | `/api/live/search/<keyword>` | Search city/station suggestions |
| `GET` | `/api/live/areas/<city>` | Area-level AQI chips for a city |
| `GET` | `/api/live/nearby?lat=&lng=` | Nearest station to coordinates |
| `GET` | `/api/live/geo/<lat>/<lon>` | Live data by GPS coordinates |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/current-aqi?city=` | Latest AQI snapshot |
| `GET` | `/api/historical?city=&hours=24` | Hourly history (used by heatmap) |
| `GET` | `/api/heatmap` | Hour × Day heatmap data |
| `GET` | `/api/statistics` | Global stats across monitored cities |
| `GET` | `/api/city-ranking` | Cities ranked by AQI |
| `GET` | `/api/city-locations` | City coordinates for map |

### AI & ML

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` / `POST` | `/api/nlp/advice` | AI guidance bot health advice and follow-up Q&A |
| `POST` | `/api/predict` | Predict AQI from pollutant inputs |

---

## 🤖 Guidance Bot

Click the **"Ask Guidance Bot"** button on the dashboard to get:

- Real-time **risk assessment** for your current city
- **Pollutant-specific** health context (PM2.5, O₃, NO₂, etc.)
- **Time-of-day** aware advice (day / evening / night)
- **Ask-anything follow-ups** for asthma patients, children, masks, outdoor exercise, and commutes
- **Numbered action steps** — mask guidance, best outdoor windows, sensitive group warnings

---

## 🌡️ AQI Scale

| Range | Category | Color |
|-------|----------|-------|
| 0–50 | Good | 🟢 |
| 51–100 | Moderate | 🟡 |
| 101–150 | Poor | 🟠 |
| 151–200 | Unhealthy | 🔴 |
| 201–300 | Severe | 🟣 |
| 301+ | Hazardous | 🔴🔴 |

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WAQI_API_TOKEN` | — | **Required.** WAQI live data token |
| `OPENAI_API_KEY` | — | **Required for AI mode.** OpenAI key for the guidance bot |
| `OPENAI_MODEL` | `gpt-5.2` | OpenAI model used by the guidance bot |
| `FLASK_PORT` | `8080` | Server port |
| `FLASK_DEBUG` | `False` | Flask debug mode |
| `LIVE_CACHE_TTL_SEC` | `120` | How long to cache live AQI responses |
| `LIVE_HISTORY_RETENTION_HOURS` | `48` | Hours of history to keep per city |
| `LIVE_MONITOR_CITIES` | *(14 defaults)* | Comma-separated list of cities to pre-monitor |

---

## 🛠️ Tech Stack

**Backend:** Python 3.9+, Flask, Requests, Pandas, NumPy, python-dotenv  
**ML:** scikit-learn (Random Forest), joblib  
**Frontend:** Vanilla HTML/CSS/JS, Chart.js, Leaflet.js  
**Data:** [WAQI API](https://waqi.info/) (live) for the dashboard; CSV artifacts are only for offline ML support

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "feat: add my feature"`
4. Push and open a Pull Request

> Make sure to never commit `.env` — use `.env.example` as a template.

---

## 📄 License

This project is for educational and research use. See [LICENSE](LICENSE) for details.

---

<div align="center">
Made with ❤️ | Real-Time Air Quality Monitoring System
</div>

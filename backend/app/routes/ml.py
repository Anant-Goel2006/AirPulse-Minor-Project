from flask import Blueprint, jsonify, request
from backend.app.services.ml import get_ml_model, get_ml_scaler, get_ml_encoders
from backend.app.utils import normalize_query_text, get_time_phase_from_iso
from backend.app.services.lstm_model import generate_lstm_forecast
from backend.app.services.openai_guidance import (
    build_guidance_base,
    generate_openai_guidance,
    merge_guidance_payload,
)

ml_bp = Blueprint("ml_bp", __name__)

@ml_bp.route("/predict/7day", methods=["GET"])
def predict_7day():
    city = str(request.args.get("city", "")).strip()
    aqi = request.args.get("aqi", 50, type=float)
    if not city:
        return jsonify({"error": "City parameter is required"}), 400
    
    # Generate LSTM mathematically simulated forecast points
    predictions = generate_lstm_forecast(city, current_aqi=aqi, current_pm25=0, current_temp=0)
    
    return jsonify({
        "city": city,
        "model": "LSTM_AutoRegressive_Sim",
        "forecast": predictions
    }), 200

@ml_bp.route("/predict", methods=["POST"])
def predict_aqi():
    try:
        model = get_ml_model()
        scaler = get_ml_scaler()
        encoders = get_ml_encoders()

        if not model or not scaler or not encoders:
            return jsonify({
                "error": "Machine Learning model is not loaded or unavailable."
            }), 503

        data = request.json
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400

        # Basic expected features: city, temperature, humidity, wind_speed, pm25, pm10, no2, so2, co, o3
        raw_city = normalize_query_text(data.get("city", "Delhi"))
        features = [
            float(data.get("temperature", 25.0)),
            float(data.get("humidity", 50.0)),
            float(data.get("wind_speed", 10.0)),
            float(data.get("pm25", 0.0)),
            float(data.get("pm10", 0.0)),
            float(data.get("no2", 0.0)),
            float(data.get("so2", 0.0)),
            float(data.get("co", 0.0)),
            float(data.get("o3", 0.0)),
        ]

        import pandas as pd
        import numpy as np

        df_input = pd.DataFrame([features], columns=[
            "temperature", "humidity", "wind_speed",
            "pm25", "pm10", "no2", "so2", "co", "o3"
        ])
        df_input_scaled = scaler.transform(df_input)

        city_encoder = encoders.get("city")
        if city_encoder:
            try:
                city_encoded = city_encoder.transform([raw_city])[0]
            except Exception:
                # Unseen city fallback
                city_encoded = 0
            df_input_scaled = np.column_stack((df_input_scaled, [city_encoded]))

        prediction = model.predict(df_input_scaled)
        predicted_aqi = max(0.0, float(prediction[0]))

        from backend.app.utils import get_category
        cat = get_category(int(round(predicted_aqi)))

        return jsonify({
            "predicted_aqi": predicted_aqi,
            "category": cat["level"],
            "color": cat["color"],
            "description": cat["text"]
        })

    except Exception as e:
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500


@ml_bp.route("/nlp/advice", methods=["GET", "POST"])
def nlp_advice():
    """Live AQI guidance with optional OpenAI-backed follow-up answers."""
    try:
        payload = request.get_json(silent=True) if request.method == "POST" else {}
        if not isinstance(payload, dict):
            payload = {}
        source = payload or request.args

        city = str(source.get("city") or "").strip()
        country = str(source.get("country") or "").strip()
        try:
            aqi = float(source.get("aqi", 0))
        except Exception:
            aqi = 0.0
        dominant = str(source.get("dominant") or "pm25").strip()
        try:
            temp = float(source.get("temp", 0))
        except Exception:
            temp = 0.0
        try:
            humidity = float(source.get("humidity", 0))
        except Exception:
            humidity = 0.0
        try:
            wind = float(source.get("wind", 0))
        except Exception:
            wind = 0.0
        time_iso = str(source.get("time_iso") or source.get("timestamp_iso") or "").strip()
        question = str(
            source.get("question")
            or source.get("message")
            or source.get("prompt")
            or ""
        ).strip()
        history = source.get("history") or source.get("messages") or []

        advice = build_guidance_base(
            city=city,
            country=country,
            aqi=aqi,
            dominant=dominant,
            temp=temp,
            humidity=humidity,
            wind=wind,
            time_iso=time_iso,
            question=question,
            history=history,
        )

        ai_payload = generate_openai_guidance(
            city=city,
            country=country,
            aqi=aqi,
            dominant=dominant,
            temp=temp,
            humidity=humidity,
            wind=wind,
            time_iso=time_iso,
            question=question,
            history=history,
        )

        if ai_payload:
            advice = merge_guidance_payload(advice, ai_payload, question=question)
            response_source = "openai"
        else:
            response_source = "rules"

        advice["source"] = response_source
        if not advice.get("assistant_reply"):
            advice["assistant_reply"] = advice.get("summary") or advice.get("primary_action") or ""

        return jsonify({"data": advice, "source": response_source}), 200
    except Exception as e:
        return jsonify({"error": f"Guidance failed: {str(e)}"}), 500

"""OpenAI-backed AQI guidance helpers."""

import json
import os
import re
from datetime import datetime

import requests


AQI_CATEGORIES = [
    {"min": 0, "max": 50, "level": "Good", "color": "#009966"},
    {"min": 51, "max": 100, "level": "Moderate", "color": "#ffde33"},
    {"min": 101, "max": 150, "level": "Poor", "color": "#ff9933"},
    {"min": 151, "max": 200, "level": "Unhealthy", "color": "#cc0033"},
    {"min": 201, "max": 300, "level": "Severe", "color": "#660099"},
    {"min": 301, "max": 999, "level": "Hazardous", "color": "#7e0023"},
]


def resolve_openai_key():
    candidates = [
        ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
        ("OPENAI_TOKEN", os.getenv("OPENAI_TOKEN")),
        ("OPENAI_KEY", os.getenv("OPENAI_KEY")),
    ]
    invalid_tokens = {
        "",
        "your_openai_api_key_here",
        "your_openai_token_here",
        "replace-me",
        "changeme",
    }
    for source, raw in candidates:
        cleaned = str(raw or "").strip().strip('"').strip("'")
        if cleaned.lower() in invalid_tokens:
            continue
        if cleaned:
            return cleaned, source
    return "", "missing"


OPENAI_API_KEY, OPENAI_API_SOURCE = resolve_openai_key()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2").strip() or "gpt-5.2"
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
OPENAI_TIMEOUT_SEC = float(os.getenv("OPENAI_TIMEOUT_SEC", "30"))


GUIDANCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "primary_action": {"type": "string"},
        "action_steps": {
            "type": "array",
            "items": {"type": "string"},
        },
        "mask_recommendation": {"type": "string"},
        "sensitive_groups_note": {"type": "string"},
        "best_time_outdoor": {"type": "string"},
        "assistant_reply": {"type": "string"},
        "follow_up_prompt": {"type": "string"},
        "emergency_note": {"type": "string"},
    },
    "required": [
        "summary",
        "primary_action",
        "action_steps",
        "mask_recommendation",
        "sensitive_groups_note",
        "best_time_outdoor",
        "assistant_reply",
        "follow_up_prompt",
        "emergency_note",
    ],
}


SYSTEM_PROMPT = (
    "You are AirPulse Guidance Bot, a calm, practical air-quality health assistant. "
    "Use the live AQI context from the app. Offer real-time precautions and prevention steps, "
    "especially for asthma patients and other sensitive groups. "
    "Be specific, actionable, and concise. "
    "Do not diagnose, prescribe, or replace a clinician. "
    "If the user mentions severe symptoms such as trouble breathing, chest pain, blue lips, confusion, "
    "or inability to speak full sentences, tell them to seek urgent medical care immediately. "
    "Avoid medical dosages or changing prescriptions. "
    "Return valid JSON only that matches the schema exactly, with no markdown, no code fences, and no extra commentary."
)


def _coerce_text(value):
    return str(value or "").strip()


def _to_float(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def get_category(aqi_value):
    try:
        val = int(round(float(aqi_value)))
    except Exception:
        return AQI_CATEGORIES[-1]
    for cat in AQI_CATEGORIES:
        if cat["min"] <= val <= cat["max"]:
            return cat
    return AQI_CATEGORIES[-1]


def get_time_phase_from_iso(time_iso):
    try:
        txt = _coerce_text(time_iso)
        if not txt:
            return "day"
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00")[:19])
        hour = dt.hour
        if 5 <= hour < 18:
            return "day"
        if 18 <= hour <= 21:
            return "evening"
        return "night"
    except Exception:
        return "day"


def _clean_step_list(values):
    out = []
    if isinstance(values, list):
        raw_items = values
    elif isinstance(values, str):
        raw_items = re.split(r"[\r\n]+", values)
    else:
        raw_items = []
    for item in raw_items:
        text = _coerce_text(item)
        if not text:
            continue
        text = re.sub(r"^[\s\-\*\u2022\d\.\)\(]+", "", text).strip()
        if text:
            out.append(text)
    # Keep the response concise and mobile-friendly.
    return out[:6]


def _question_addon(question):
    q = _coerce_text(question).lower()
    if not q:
        return ""

    extras = []
    if "asthma" in q:
        extras.append(
            "For asthma patients, keep the prescribed rescue inhaler close, avoid hard outdoor exercise, "
            "and stop activity if wheezing, chest tightness, or unusual coughing starts."
        )
    if any(token in q for token in ("mask", "face covering", "face mask")):
        extras.append(
            "If you must go outside, a well-fitted N95 or FFP2-style mask is usually more useful than a loose cloth mask."
        )
    if any(token in q for token in ("exercise", "workout", "run", "jog")):
        extras.append(
            "Choose an indoor alternative when AQI is elevated, or keep outdoor exercise short and away from traffic."
        )
    if any(token in q for token in ("children", "child", "kids", "school")):
        extras.append(
            "Children should spend less time outdoors when pollution rises, and school drop-off or playtime should be shortened."
        )
    if any(token in q for token in ("pregnant", "elder", "older", "senior")):
        extras.append(
            "Pregnant people and older adults should use a stricter exposure limit and prefer indoor spaces when AQI worsens."
        )

    if not extras:
        return ""
    return " " + " ".join(extras)


def build_guidance_base(city, country, aqi, dominant, temp, humidity, wind, time_iso, question="", history=None):
    aqi_val = max(0.0, _to_float(aqi, 0.0))
    cat = get_category(aqi_val)
    risk = cat["level"]
    phase = get_time_phase_from_iso(time_iso)
    dominant_key = _coerce_text(dominant).lower() or "pm25"

    pollutant_hint = {
        "pm25": "Fine particles are elevated, so lungs can be irritated quickly.",
        "pm10": "Dust-like particles are high; prolonged exposure may trigger coughing.",
        "o3": "Ground-level ozone is elevated and can cause throat irritation outdoors.",
        "no2": "Nitrogen dioxide is elevated, especially risky near traffic corridors.",
        "so2": "Sulfur dioxide is elevated and may aggravate asthma symptoms.",
        "co": "Carbon monoxide exposure risk is higher; ensure good indoor ventilation.",
    }
    risk_precautions = {
        "Good": [
            "Normal outdoor activity is generally safe.",
            "Keep hydration steady during longer outdoor sessions.",
            "Sensitive individuals should still monitor any unusual symptoms.",
        ],
        "Moderate": [
            "Sensitive groups should reduce long, intense outdoor exercise.",
            "Prefer parks or low-traffic routes instead of congested roads.",
            "If irritation starts, move indoors and rest.",
        ],
        "Poor": [
            "Limit prolonged outdoor exposure, especially for children and elders.",
            "Avoid outdoor workouts near traffic-heavy areas.",
            "Use a well-fitted mask if you must stay outside for long periods.",
        ],
        "Unhealthy": [
            "Reduce outdoor time and postpone non-essential outdoor activities.",
            "Keep windows closed during peak traffic and dusty periods.",
            "Use an N95 or FFP2-type mask when stepping outside.",
        ],
        "Severe": [
            "Avoid outdoor exertion and keep activities indoors.",
            "Run an air purifier in occupied rooms if available.",
            "Limit children, elderly people, and respiratory patients to indoor spaces.",
        ],
        "Hazardous": [
            "Stay indoors as much as possible and avoid all outdoor exertion.",
            "Seal indoor air leaks where possible and run air cleaning continuously.",
            "Go outside only if essential, with a high-filtration mask.",
        ],
    }
    risk_measures = {
        "Good": [
            "Track AQI every few hours before planning long outdoor sessions.",
            "Maintain indoor ventilation when outdoor air remains stable.",
            "Carry water and avoid smoke exposure sources.",
        ],
        "Moderate": [
            "Schedule walks in cleaner periods and avoid rush-hour traffic zones.",
            "Keep quick-relief inhalers accessible for sensitive users.",
            "Use recirculation mode in vehicles during congestion.",
        ],
        "Poor": [
            "Shift exercise indoors or to low-pollution time windows.",
            "Use masks during commute and near construction areas.",
            "Clean dust from indoor surfaces more often during bad-air days.",
        ],
        "Unhealthy": [
            "Postpone strenuous activities until AQI improves.",
            "Ventilate home only when outdoor levels temporarily drop.",
            "Use saline rinses where medically appropriate and if recommended by a clinician.",
        ],
        "Severe": [
            "Create a clean-air room with a purifier and closed windows.",
            "Restrict exposure for high-risk groups and monitor symptoms closely.",
            "Consult a clinician if breathlessness, wheeze, or chest pain appears.",
        ],
        "Hazardous": [
            "Activate emergency indoor air-protection routine immediately.",
            "Avoid opening windows and doors except when necessary.",
            "Seek medical help promptly if severe respiratory discomfort occurs.",
        ],
    }
    phase_tip = {
        "day": "Midday sun can increase secondary pollutants in some regions.",
        "evening": "Evening traffic can increase roadside exposure.",
        "night": "Night-time inversion may trap pollutants near ground level.",
    }

    humidity_val = _to_float(humidity, 0.0)
    temp_val = _to_float(temp, 0.0)
    wind_val = _to_float(wind, 0.0)
    climate_note = ""
    if humidity_val >= 75:
        climate_note = " High humidity can make breathing feel heavier for sensitive users."
    elif wind_val >= 8:
        climate_note = " Strong wind may disperse some pollutants but can also carry dust locally."
    elif temp_val >= 34:
        climate_note = " Hot weather can increase discomfort during exposure."

    if aqi_val <= 100:
        best_time_outdoor = "Early morning or post-rain periods are generally preferred."
    elif aqi_val <= 200:
        best_time_outdoor = "Keep outdoor tasks short and choose lower-traffic hours."
    else:
        best_time_outdoor = "Avoid outdoor activity until AQI improves."

    if phase == "evening":
        best_time_outdoor = "Prefer short outdoor tasks before heavy evening traffic."
    elif phase == "night" and aqi_val > 150:
        best_time_outdoor = "Delay outdoor exposure until cleaner daytime windows."

    if aqi_val <= 100:
        mask_recommendation = "Mask is optional for most people; sensitive users may prefer light protection."
        primary_action = "Stay aware and keep outdoor activity moderate if you are sensitive."
    elif aqi_val <= 200:
        mask_recommendation = "Use a well-fitted N95 or FFP2 mask for longer outdoor exposure."
        primary_action = "Reduce prolonged outdoor exertion and protect sensitive groups."
    else:
        mask_recommendation = "Use a high-filtration N95 or FFP2 mask for any essential outdoor movement."
        primary_action = "Stay indoors as much as possible and avoid outdoor exertion."

    sensitive_groups_note = (
        "Children, elderly adults, pregnant women, and people with asthma, COPD, or heart disease "
        "should follow stricter exposure limits."
    )

    city_label = _coerce_text(city).strip() or "Unknown"
    country_label = _coerce_text(country).strip()
    city_full = f"{city_label}, {country_label}" if country_label else city_label
    summary = (
        f"In {city_full}, AQI is {int(round(aqi_val))} ({risk}). "
        f"{pollutant_hint.get(dominant_key, 'Air pollution levels require cautious exposure planning.')} "
        f"{phase_tip[phase]}{climate_note}"
    )

    precautions = risk_precautions[risk][:3]
    measures = risk_measures[risk][:3]
    action_steps = _clean_step_list(precautions + measures)
    if phase == "night" and aqi_val > 100:
        action_steps.append("Keep bedroom windows closed overnight to reduce indoor particle buildup.")

    assistant_reply = summary if not _coerce_text(question) else (
        f"{primary_action}{_question_addon(question)}"
    ).strip()
    follow_up_prompt = "Ask me about asthma-specific steps, mask choice, outdoor exercise, or school/work commute plans."
    if "asthma" in _coerce_text(question).lower():
        follow_up_prompt = "If you want, I can also tailor this into a morning, commute, or school plan for asthma care."
    emergency_note = (
        "If breathing becomes hard, symptoms worsen, or chest pain appears, seek urgent medical care."
    )

    return {
        "city": city_label,
        "country": country_label,
        "aqi": round(aqi_val, 1),
        "risk_level": risk,
        "color": cat["color"],
        "summary": summary,
        "primary_action": primary_action,
        "action_steps": action_steps,
        "precautions": precautions,
        "measures": measures,
        "best_time_outdoor": best_time_outdoor,
        "mask_recommendation": mask_recommendation,
        "sensitive_groups_note": sensitive_groups_note,
        "assistant_reply": assistant_reply,
        "follow_up_prompt": follow_up_prompt,
        "emergency_note": emergency_note,
        "source": "rules",
    }


def _history_to_text(history):
    lines = []
    if not isinstance(history, list):
        return "None"
    for item in history[-6:]:
        if isinstance(item, dict):
            role = _coerce_text(item.get("role") or item.get("speaker") or "user").lower()
            label = "Assistant" if role == "assistant" else "User"
            content = _coerce_text(item.get("content") or item.get("text") or item.get("message"))
            if content:
                lines.append(f"{label}: {content}")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            label = "Assistant" if _coerce_text(item[0]).lower() == "assistant" else "User"
            content = _coerce_text(item[1])
            if content:
                lines.append(f"{label}: {content}")
        elif isinstance(item, str):
            txt = item.strip()
            if txt:
                lines.append(f"User: {txt}")
    return "\n".join(lines) if lines else "None"


def build_guidance_prompt(city, country, aqi, dominant, temp, humidity, wind, time_iso, question="", history=None):
    context = {
        "city": _coerce_text(city),
        "country": _coerce_text(country),
        "aqi": round(_to_float(aqi, 0.0), 1),
        "dominant_pollutant": _coerce_text(dominant).lower() or "pm25",
        "temperature_c": _to_float(temp, 0.0),
        "humidity_percent": _to_float(humidity, 0.0),
        "wind_speed": _to_float(wind, 0.0),
        "time_iso": _coerce_text(time_iso),
        "time_phase": get_time_phase_from_iso(time_iso),
        "question": _coerce_text(question),
    }
    return (
        "Use the live AQI context below and answer the user's latest question.\n"
        "Return JSON only that matches the schema.\n\n"
        f"Live context:\n{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
        f"Recent conversation:\n{_history_to_text(history)}\n\n"
        f"Latest user question:\n{_coerce_text(question) or 'Provide general precautions for the current AQI and invite a follow-up about asthma, masks, children, or outdoor exercise.'}\n"
    )


def _extract_output_text(payload):
    if not isinstance(payload, dict):
        return ""
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()
    outputs = payload.get("output") or []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        content = item.get("content") or []
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            txt = chunk.get("text")
            if isinstance(txt, str) and txt.strip():
                return txt.strip()
    return ""


def _strip_code_fences(text):
    txt = _coerce_text(text)
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.IGNORECASE)
        txt = re.sub(r"\s*```$", "", txt)
    return txt.strip()


def generate_openai_guidance(city, country, aqi, dominant, temp, humidity, wind, time_iso, question="", history=None):
    if not OPENAI_API_KEY:
        return None

    payload = {
        "model": OPENAI_MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": build_guidance_prompt(
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
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "aqi_guidance",
                "schema": GUIDANCE_SCHEMA,
                "strict": True,
            }
        },
        "temperature": 0.2,
        "max_output_tokens": 650,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{OPENAI_BASE_URL}/responses",
            headers=headers,
            json=payload,
            timeout=OPENAI_TIMEOUT_SEC,
        )
    except requests.RequestException as exc:
        print(f"[WARN] OpenAI guidance request failed: {exc}")
        return None

    if not resp.ok:
        snippet = _coerce_text(resp.text)[:300]
        print(f"[WARN] OpenAI guidance API returned {resp.status_code}: {snippet}")
        return None

    try:
        data = resp.json()
    except Exception as exc:
        print(f"[WARN] OpenAI guidance response was not valid JSON: {exc}")
        return None

    raw_text = _strip_code_fences(_extract_output_text(data))
    if not raw_text:
        return None

    try:
        parsed = json.loads(raw_text)
    except Exception:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw_text[start : end + 1])
            except Exception:
                parsed = {"assistant_reply": raw_text}
        else:
            parsed = {"assistant_reply": raw_text}

    if not isinstance(parsed, dict):
        return None

    return parsed


def merge_guidance_payload(base_payload, ai_payload, question=""):
    merged = dict(base_payload or {})
    ai = ai_payload if isinstance(ai_payload, dict) else {}

    def take_text(*keys):
        for key in keys:
            value = ai.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def take_list(*keys):
        for key in keys:
            value = ai.get(key)
            if isinstance(value, list):
                cleaned = [str(item).strip() for item in value if str(item).strip()]
                if cleaned:
                    return cleaned[:6]
            elif isinstance(value, str):
                cleaned = _clean_step_list(value)
                if cleaned:
                    return cleaned
        return []

    for key in (
        "summary",
        "primary_action",
        "mask_recommendation",
        "sensitive_groups_note",
        "best_time_outdoor",
        "assistant_reply",
        "follow_up_prompt",
        "emergency_note",
        "risk_level",
    ):
        text = take_text(key)
        if text:
            merged[key] = text

    steps = take_list("action_steps", "steps")
    if steps:
        merged["action_steps"] = steps

    for key in ("precautions", "measures"):
        value = ai.get(key)
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if cleaned:
                merged[key] = cleaned[:3]

    if question and not merged.get("assistant_reply"):
        merged["assistant_reply"] = merged.get("primary_action") or merged.get("summary") or ""

    if not merged.get("assistant_reply"):
        merged["assistant_reply"] = merged.get("summary") or merged.get("primary_action") or ""

    merged["source"] = "openai"
    return merged

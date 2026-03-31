import time
import numpy as np
from datetime import datetime, timedelta
from backend.app.utils import get_category

def generate_lstm_forecast(city, current_aqi, current_pm25, current_temp):
    """
    Simulates a 7-day localized Long Short-Term Memory (LSTM) forecast.
    In a full production environment, this would load a PyTorch .pt model.
    Here we use an autoregressive simulation bridging current data with 
    historical variance parameters to project 7 days into the future.
    """
    forecast = []
    base_time = int(time.time())
    
    # LSTM simulation parameters
    volatility = 0.15
    trend = -0.02 if current_aqi > 150 else 0.01  # Regression to the mean
    
    current_val = float(current_aqi)
    
    for day in range(1, 8):
        # Apply simulated LSTM cell state transitions (sinusoidal + noise + trend)
        cell_memory = np.sin(day * np.pi / 4) * (current_val * 0.1)
        noise = np.random.normal(0, current_val * volatility)
        
        # Calculate next state
        next_val = current_val * (1 + trend) + cell_memory + noise
        next_val = max(10, min(500, next_val)) # clamp to viable AQI bounds
        
        # Build payload
        forecast_ts = base_time + (day * 86400)
        dt_obj = datetime.fromtimestamp(forecast_ts)
        cat = get_category(int(round(next_val)))
        
        forecast.append({
            "day_epoch": forecast_ts,
            "date": dt_obj.strftime("%Y-%m-%d"),
            "day_name": dt_obj.strftime("%A"),
            "predicted_aqi": int(round(next_val)),
            "level": cat["level"],
            "color": cat["color"]
        })
        
        # update state for next iteration
        current_val = next_val
        
    return forecast

# index.py
# api/index.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import pandas as pd
import numpy as np

# --- 1. Pydantic Model for Request Body ---
class RequestBody(BaseModel):
    """Defines the structure of the incoming JSON body."""
    # List of regions to filter (e.g., ["amer", "emea"])
    regions: List[str]
    # Latency threshold in milliseconds (e.g., 180)
    threshold_ms: float = Field(..., gt=0)

# --- 2. Data Loading (Executed once at server startup) ---
try:
    # Load the JSON data into a pandas DataFrame
    # Using '..' to step up from the 'api' directory to the project root
    TELEMETRY_DF = pd.read_json('../q-vercel-latency.json', lines=True)

    # Convert 'latency' and 'uptime' to numeric, handling errors if any
    TELEMETRY_DF['latency'] = pd.to_numeric(TELEMETRY_DF['latency'], errors='coerce')
    TELEMETRY_DF['uptime'] = pd.to_numeric(TELEMETRY_DF['uptime'], errors='coerce')
    
    # Drop rows where conversion failed (should not happen with sample data)
    TELEMETRY_DF.dropna(subset=['latency', 'uptime'], inplace=True)
    
except FileNotFoundError:
    print("FATAL ERROR: 'q-vercel-latency.json' not found. Please check the path.")
    TELEMETRY_DF = pd.DataFrame()
except Exception as e:
    print(f"FATAL ERROR during data load: {e}")
    TELEMETRY_DF = pd.DataFrame()

# --- 3. FastAPI Application Setup ---
app = FastAPI()

# --- 4. CORS Middleware ---
# Enable CORS for POST requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["POST", "GET"], # Allow POST and GET (for root/docs)
    allow_headers=["*"],
)

# --- 5. API Endpoint ---
@app.post("/api")
def get_metrics(data: RequestBody) -> Dict[str, Dict[str, float]]:
    """
    Accepts regions and a latency threshold. Returns mean and p95 latency, 
    mean uptime, and breach count per region.
    """
    
    # Initialize the results dictionary
    metrics_result: Dict[str, Dict[str, float]] = {}

    # Check if the dataframe is empty (data loading failed)
    if TELEMETRY_DF.empty:
        return {"error": "Telemetry data could not be loaded."}

    # Iterate over each requested region
    for region in data.regions:
        # 1. Filter the DataFrame for the current region
        region_df = TELEMETRY_DF[TELEMETRY_DF['region'] == region]
        
        if region_df.empty:
            # Skip regions with no data
            continue

        # 2. Calculate Metrics
        
        # Mean Latency
        avg_latency = region_df['latency'].mean()
        
        # P95 Latency (95th percentile)
        # np.percentile requires an array-like object
        p95_latency = np.percentile(region_df['latency'], 95)
        
        # Mean Uptime (Average)
        avg_uptime = region_df['uptime'].mean()
        
        # Breaches (Count where latency is above the threshold)
        breaches = (region_df['latency'] > data.threshold_ms).sum()

        # 3. Store Results (rounding to 3 decimal places for clean JSON)
        metrics_result[region] = {
            "avg_latency": round(avg_latency, 3),
            "p95_latency": round(p95_latency, 3),
            "avg_uptime": round(avg_uptime, 3),
            "breaches": float(breaches) # Ensure count is returned as a number
        }

    return metrics_result

# --- 6. Root Endpoint (Optional) ---
@app.get("/")
def read_root():
    return {"message": "Telemetry Metrics API is running. POST to /api."}

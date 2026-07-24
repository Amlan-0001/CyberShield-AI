from pathlib import Path
import sys
from io import StringIO

import pandas as pd

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

# ==========================================================
# Configure Python Path
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[1]

URL_SRC = BASE_DIR / "url_detection" / "src"
NETWORK_SRC = BASE_DIR / "network_detection"

for path in [URL_SRC, NETWORK_SRC]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

# ==========================================================
# Import Predictors
# ==========================================================

from predictor import URLPredictor
from network_predictor import NetworkThreatPredictor

# ==========================================================
# FastAPI App
# ==========================================================

app = FastAPI(
    title="CyberShield AI",
    description="AI-powered URL Phishing & Network Threat Detection API",
    version="2.0.0",
)

# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# Load Models
# ==========================================================

try:
    url_predictor = URLPredictor()
    network_predictor = NetworkThreatPredictor()

    print("✅ URL Model Loaded")
    print("✅ Network Model Loaded")

except Exception as e:
    raise RuntimeError(f"Failed to load ML models:\n{e}")

# ==========================================================
# Request / Response Models
# ==========================================================

class URLRequest(BaseModel):
    url: HttpUrl


class URLPredictionResponse(BaseModel):
    prediction: str
    legitimate_probability: float
    phishing_probability: float


# ==========================================================
# Health Route
# ==========================================================

@app.get("/", tags=["Health"])
def health_check():

    return {
        "status": "success",
        "message": "CyberShield AI API is running."
    }

# ==========================================================
# URL Prediction
# ==========================================================

@app.post(
    "/predict-url",
    response_model=URLPredictionResponse,
    tags=["URL Detection"],
)
def predict_url(request: URLRequest):

    try:

        result = url_predictor.predict(str(request.url))

        prediction = (
            "Legitimate"
            if result["prediction"] == 0
            else "Phishing"
        )

        return URLPredictionResponse(
            prediction=prediction,
            legitimate_probability=result["legitimate_probability"],
            phishing_probability=result["phishing_probability"],
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"URL Prediction Failed : {e}"
        )

# ==========================================================
# Network Prediction
# ==========================================================

@app.post(
    "/predict-network",
    tags=["Network Detection"],
)
async def predict_network(
    file: UploadFile = File(...)
):

    try:

        # Accept CSV only
        if not file.filename.endswith(".csv"):

            raise HTTPException(
                status_code=400,
                detail="Please upload a CSV file."
            )

        # Read uploaded CSV
        contents = await file.read()

        df = pd.read_csv(
            StringIO(contents.decode("utf-8"))
        )

        # Remove target column if present
        if "Attack Type" in df.columns:
            df = df.drop(columns=["Attack Type"])

        # Predict
        predictions = network_predictor.predict(df)

        return {
            "filename": file.filename,
            "total_records": len(predictions),
            "predictions": predictions
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Network Prediction Failed : {e}"
        )
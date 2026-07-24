import joblib
from pathlib import Path

from feature_engineering import FeatureExtractor


class URLPredictor:
    def __init__(self):
        # Load the trained model once
        model_path = (
            Path(__file__).resolve().parents[1]
            / "models"
            / "xgboost_url_detector.pkl"
        )

        self.model = joblib.load(model_path)
        self.extractor = FeatureExtractor()

    def predict(self, url: str):
        # Extract features
        features = self.extractor.extract_features(url)

        # Predict
        prediction = self.model.predict(features)[0]
        probability = self.model.predict_proba(features)[0]

        return {
            "prediction": int(prediction),
            "legitimate_probability": float(probability[0]),
            "phishing_probability": float(probability[1]),
        }
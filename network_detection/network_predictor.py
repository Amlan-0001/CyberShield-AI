from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from network_detection.network_attack_metadata import ATTACK_INFO


class NetworkThreatPredictor:
    """
    Predict network attacks using the trained XGBoost model.
    """

    def __init__(self):
        """
        Load the trained XGBoost model and label encoder.
        """

        # Base directory of this file
        base_dir = Path(__file__).resolve().parent

        # Absolute paths to model files
        model_path = base_dir / "models" / "network_detector.pkl"
        encoder_path = base_dir / "models" / "label_encoder.pkl"

        # Load model and encoder
        self.model = joblib.load(model_path)
        self.label_encoder = joblib.load(encoder_path)

    def predict(self, input_data):
        """
        Predict attack types for the given network traffic.

        Parameters
        ----------
        input_data : pandas.DataFrame
            DataFrame containing the network features.

        Returns
        -------
        list
            List of prediction dictionaries.
        """

        # Validate input
        if not isinstance(input_data, pd.DataFrame):
            raise ValueError("Input must be a pandas DataFrame.")

        # Predict probabilities
        probabilities = self.model.predict_proba(input_data)

        # Predicted class indices
        predicted_indices = np.argmax(probabilities, axis=1)

        # Convert indices to attack names
        predicted_labels = self.label_encoder.inverse_transform(
            predicted_indices
        )

        results = []

        for i, attack in enumerate(predicted_labels):

            confidence = round(
                float(np.max(probabilities[i])) * 100,
                2
            )

            # Get attack metadata
            info = ATTACK_INFO.get(
                attack,
                {
                    "risk_level": "Unknown",
                    "description": "No description available.",
                    "recommendation": "No recommendation available."
                }
            )

            results.append(
                {
                    "prediction": attack,
                    "confidence": confidence,
                    "risk_level": info["risk_level"],
                    "description": info["description"],
                    "recommendation": info["recommendation"]
                }
            )

        return results
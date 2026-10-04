from flask import Flask, request, jsonify
import joblib
import numpy as np

app = Flask(__name__)

model = joblib.load("model.joblib")
target_names = joblib.load("target_names.joblib")


def validate_feature_array(features, field_name="features"):
    if not isinstance(features, list):
        return None, f"'{field_name}' must be a list of 4 numeric values."

    if len(features) != 4:
        return None, f"'{field_name}' must contain exactly 4 values."

    try:
        numeric_features = [float(value) for value in features]
    except (TypeError, ValueError):
        return None, f"All values in '{field_name}' must be numeric."

    return numeric_features, None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    if "features" not in data:
        return jsonify({"error": "Missing required key: 'features'."}), 400

    features, error = validate_feature_array(data["features"])
    if error:
        return jsonify({"error": error}), 400

    sample = np.array(features).reshape(1, -1)
    prediction_index = int(model.predict(sample)[0])
    probabilities = model.predict_proba(sample)[0]

    return jsonify({
        "predicted_class": str(target_names[prediction_index]),
        "probabilities": {
            str(class_name): float(probability)
            for class_name, probability in zip(target_names, probabilities)
        }
    }), 200


@app.route("/predict_batch", methods=["POST"])
def predict_batch():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    if "samples" not in data:
        return jsonify({"error": "Missing required key: 'samples'."}), 400

    samples = data["samples"]
    if not isinstance(samples, list) or len(samples) == 0:
        return jsonify({"error": "'samples' must be a non-empty list of feature arrays."}), 400

    validated_samples = []
    for index, sample in enumerate(samples):
        features, error = validate_feature_array(sample, f"samples[{index}]")
        if error:
            return jsonify({"error": error}), 400
        validated_samples.append(features)

    sample_array = np.array(validated_samples)
    prediction_indices = model.predict(sample_array)
    probability_rows = model.predict_proba(sample_array)

    predictions = []
    for prediction_index, probabilities in zip(prediction_indices, probability_rows):
        predictions.append({
            "predicted_class": str(target_names[int(prediction_index)]),
            "probabilities": {
                str(class_name): float(probability)
                for class_name, probability in zip(target_names, probabilities)
            }
        })

    return jsonify({"predictions": predictions}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)

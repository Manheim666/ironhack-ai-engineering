# Iris Model Deployment

## What the model does

This project deploys a scikit-learn Random Forest classifier trained on the Iris dataset. The model receives four numeric flower measurements: sepal length, sepal width, petal length, and petal width. It predicts one of three Iris species: setosa, versicolor, or virginica. The Flask API returns both the predicted class name and the probability assigned to each class.

## How to run

1. Install the required Python packages:

```bash
pip install flask joblib requests scikit-learn numpy pandas
```

2. Run the notebook to train and serialize the model:

```bash
jupyter notebook m4-09-model-deployment.ipynb
```

3. Confirm these files exist in the project root:

```text
model.joblib
target_names.joblib
app.py
```

4. Start the Flask API:

```bash
python app.py
```

5. Open another terminal or use the notebook to send requests to:

```text
http://localhost:5000
```

## API specification

### GET /health

Checks whether the service is running.

**Request body:** none

**Success response:** `200 OK`

```json
{
  "status": "healthy"
}
```

### POST /predict

Predicts the species for one Iris sample.

**Request body:**

```json
{
  "features": [5.1, 3.5, 1.4, 0.2]
}
```

**Validation rules:**

- `features` is required.
- `features` must contain exactly 4 values.
- All values must be numeric.

**Success response:** `200 OK`

```json
{
  "predicted_class": "setosa",
  "probabilities": {
    "setosa": 1.0,
    "versicolor": 0.0,
    "virginica": 0.0
  }
}
```

**Error response:** `400 Bad Request`

```json
{
  "error": "Missing required key: 'features'."
}
```

### POST /predict_batch

Predicts the species for multiple Iris samples.

**Request body:**

```json
{
  "samples": [
    [5.1, 3.5, 1.4, 0.2],
    [6.2, 3.4, 5.4, 2.3]
  ]
}
```

**Validation rules:**

- `samples` is required.
- `samples` must be a non-empty list.
- Each sample must contain exactly 4 numeric values.

**Success response:** `200 OK`

```json
{
  "predictions": [
    {
      "predicted_class": "setosa",
      "probabilities": {
        "setosa": 1.0,
        "versicolor": 0.0,
        "virginica": 0.0
      }
    },
    {
      "predicted_class": "virginica",
      "probabilities": {
        "setosa": 0.0,
        "versicolor": 0.01,
        "virginica": 0.99
      }
    }
  ]
}
```

## Example requests

### Health check with curl

```bash
curl http://localhost:5000/health
```

### Single prediction with curl

```bash
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [5.1, 3.5, 1.4, 0.2]}'
```

### Batch prediction with curl

```bash
curl -X POST http://localhost:5000/predict_batch \
  -H "Content-Type: application/json" \
  -d '{"samples": [[5.1, 3.5, 1.4, 0.2], [6.2, 3.4, 5.4, 2.3]]}'
```

### Python requests example

```python
import requests

response = requests.post(
    "http://localhost:5000/predict",
    json={"features": [5.1, 3.5, 1.4, 0.2]}
)

print(response.status_code)
print(response.json())
```

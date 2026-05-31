"""Script de exemplo para treinar modelos JUNO via API."""

import os

import requests

BASE_URL = os.getenv("JUNO_API_URL", "http://localhost:8000")
USERNAME = os.getenv("JUNO_EXAMPLE_USERNAME")
PASSWORD = os.getenv("JUNO_EXAMPLE_PASSWORD")
TOKEN = None


def login():
    global TOKEN
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Defina JUNO_EXAMPLE_USERNAME e JUNO_EXAMPLE_PASSWORD para executar o exemplo.")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": USERNAME, "password": PASSWORD},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    TOKEN = body["access_token"]
    print(f"Logado: {body['user']['email']}")


def train_regression(company_id=1):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {"name": "Previsao de Custo de Producao", "samples": 2000}
    response = requests.post(
        f"{BASE_URL}/ml/{company_id}/train/regression",
        headers=headers,
        json=payload,
        timeout=30,
    )
    body = response.json()
    print(f"Regressao: {body}")
    return body


def train_classification(company_id=1):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {"name": "Classificacao de Risco de Pedido", "samples": 1500}
    response = requests.post(
        f"{BASE_URL}/ml/{company_id}/train/classification",
        headers=headers,
        json=payload,
        timeout=30,
    )
    body = response.json()
    print(f"Classificacao: {body}")
    return body


def train_anomaly(company_id=1):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {"name": "Deteccao de Anomalias na Producao", "samples": 3000}
    response = requests.post(
        f"{BASE_URL}/ml/{company_id}/train/anomaly",
        headers=headers,
        json=payload,
        timeout=30,
    )
    body = response.json()
    print(f"Anomalia: {body}")
    return body


def predict(model_id, input_data):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.post(
        f"{BASE_URL}/ml/1/predict/{model_id}",
        headers=headers,
        json=input_data,
        timeout=30,
    )
    body = response.json()
    print(f"Predicao: {body}")
    return body


if __name__ == "__main__":
    login()

    reg = train_regression()
    clf = train_classification()
    train_anomaly()

    if reg.get("model_id"):
        predict(
            reg["model_id"],
            {
                "planned_qty": 500,
                "material_cost": 5000,
                "labor_hours": 40,
                "complexity": 5,
            },
        )

    if clf.get("model_id"):
        predict(
            clf["model_id"],
            {
                "order_value": 50000,
                "customer_history": 25,
                "payment_delay": 45,
                "sector_risk": 3,
            },
        )

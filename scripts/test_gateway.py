#!/usr/bin/env python3
"""
Test NGINX API Gateway với API Key authentication.
"""
import requests
import json

GATEWAY_URL = "http://35.240.244.150"   # EXTERNAL-IP của NGINX ingress
# Nếu chưa có domain, dùng trực tiếp IP với Host header
HOST = "api.phobert-medical.example.com"

VALID_KEY   = "sk-admin-changeme-abc123"
INVALID_KEY = "sk-invalid-key"

PAYLOAD = {
    "instances": [
        "Bệnh nhân Nguyễn Văn A, 35 tuổi, trú tại Cầu Giấy, Hà Nội.",
    ]
}

def test(desc, headers, expected_status):
    resp = requests.post(
        f"{GATEWAY_URL}/api/v1/predict",
        json=PAYLOAD,
        headers={"Host": HOST, **headers},
        timeout=30,
    )
    icon = "✅" if resp.status_code == expected_status else "❌"
    print(f"{icon} {desc}: HTTP {resp.status_code} (expected {expected_status})")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   profiles: {json.dumps(data.get('profiles', []), ensure_ascii=False)}")
    else:
        print(f"   body: {resp.text[:100]}")
    return resp.status_code == expected_status


print("=" * 55)
print("  NGINX API Gateway — Auth Tests")
print("=" * 55)

results = [
    test("No API key",      {},                              401),
    test("Invalid API key", {"X-API-Key": INVALID_KEY},     403),
    test("Valid API key",   {"X-API-Key": VALID_KEY},        200),
]

print(f"\n{sum(results)}/{len(results)} tests passed")
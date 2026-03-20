import requests
import json

INGRESS_IP   = "34.142.155.250"
MODEL_NAME   = "phobert-medical"
NAMESPACE    = "model-serving"

# KServe routing qua Istio Ingress Gateway
URL = f"http://{INGRESS_IP}/v1/models/{MODEL_NAME}:predict"
HEADERS = {
    "Content-Type": "application/json",
    # Host header để Istio VirtualService route đúng InferenceService
    "Host": f"{MODEL_NAME}.{NAMESPACE}.{INGRESS_IP}.sslip.io",
}

if __name__ == "__main__":
    data = {
        "instances": ["Bệnh nhân Nguyễn Văn A, 35 tuổi, trú tại Cầu Giấy, Hà Nội. ",
                    "Nhập viện ngày 20/01/2026 với triệu chứng sốt cao và ho kéo dài."]
    }

    print(f"Sending request to : {URL}")
    print(f"Host header        : {HEADERS['Host']}")
    print(f"Payload            : {json.dumps(data, ensure_ascii=False)}\n")

    response = requests.post(URL, json=data, headers=HEADERS)

    if response.status_code == 200:
        print("✅ Kết quả dự đoán:")
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    else:
        print(f"❌ Lỗi {response.status_code}:")
        print(response.text)
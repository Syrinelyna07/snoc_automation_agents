import os
import sys

import httpx

api_key = os.getenv("VLLM_API_KEY", "")

deployments = {
    "Qwen Analyzer": os.getenv("VLLM_QWEN_BASE_URL", ""),
    "Gemma Verifier": os.getenv("VLLM_GEMMA_BASE_URL", ""),
}

if not api_key:
    raise SystemExit("VLLM_API_KEY is missing.")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json",
}

failed = False

for name, base_url in deployments.items():
    if not base_url:
        print(f"{name}: base URL is missing.")
        failed = True
        continue

    url = base_url.rstrip("/") + "/models"

    try:
        response = httpx.get(
            url,
            headers=headers,
            timeout=30,
        )
        print(f"{name}: HTTP {response.status_code}")

        if response.is_success:
            payload = response.json()
            models = [
                item.get("id")
                for item in payload.get("data", [])
            ]
            print("  Models:", models)
        else:
            print("  Response:", response.text[:300])
            failed = True

    except Exception as exc:
        print(f"{name}: ERROR: {exc}")
        failed = True

if failed:
    sys.exit(1)

print("SUCCESS: both vLLM deployments are reachable.")

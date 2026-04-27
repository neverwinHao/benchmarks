"""
Lightweight reverse proxy that adds Azure AD managed-identity tokens
to requests and forwards them to Azure OpenAI.

Listen: 0.0.0.0:4142
Forward: https://aoai4datadev.openai.azure.com/openai/...

Routes:
- /v1/responses -> /openai/responses (no deployment path, api-version=2025-03-01-preview)
- /v1/chat/completions -> /openai/deployments/{dep}/chat/completions (api-version=2024-12-01-preview)
"""

import random
import logging

import httpx
import uvicorn
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("azure-proxy")

IDENTITY_ID = "a6b937c3-5c52-4902-ac1d-c740b0d2acc1"
AZURE_ENDPOINT = "https://aoai4datadev.openai.azure.com"
SCOPE = "https://cognitiveservices.azure.com/.default"
DEPLOYMENTS = ["gpt-5"]

credential = DefaultAzureCredential(managed_identity_client_id=IDENTITY_ID)
_token_provider = get_bearer_token_provider(credential, SCOPE)
_client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0))


def pick_deployment():
    return random.choice(DEPLOYMENTS)


async def app(scope, receive, send):
    if scope["type"] != "http":
        return

    path = scope["path"]
    method = scope["method"]

    body = b""
    while True:
        msg = await receive()
        body += msg.get("body", b"")
        if not msg.get("more_body", False):
            break

    req_headers = {k.decode(): v.decode() for k, v in scope["headers"]}
    token = _token_provider()

    # Route based on endpoint
    if "/responses" in path:
        # Responses API: /openai/responses (no deployment), newer api-version
        target_url = f"{AZURE_ENDPOINT}/openai/responses?api-version=2025-03-01-preview"
        log.info(f"{method} {path} -> /openai/responses")
    else:
        # Chat Completions and other endpoints: use deployment path
        deployment = pick_deployment()
        if path.startswith("/v1/"):
            azure_path = path[3:]
        else:
            azure_path = path
        target_url = f"{AZURE_ENDPOINT}/openai/deployments/{deployment}{azure_path}?api-version=2024-12-01-preview"
        log.info(f"{method} {path} -> {deployment}{azure_path}")

    fwd_headers = {
        "authorization": f"Bearer {token}",
        "content-type": req_headers.get("content-type", "application/json"),
    }

    try:
        resp = await _client.request(method, target_url, headers=fwd_headers, content=body)
    except Exception as e:
        log.error(f"Upstream error: {e}")
        await send({"type": "http.response.start", "status": 502, "headers": [[b"content-type", b"text/plain"]]})
        await send({"type": "http.response.body", "body": str(e).encode()})
        return

    resp_headers = [[k.encode(), v.encode()] for k, v in resp.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-encoding", "content-length")]
    resp_headers.append([b"content-length", str(len(resp.content)).encode()])

    await send({"type": "http.response.start", "status": resp.status_code, "headers": resp_headers})
    await send({"type": "http.response.body", "body": resp.content})

    if resp.status_code >= 400:
        log.warning(f"Upstream {resp.status_code}: {resp.text[:500]}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4142, log_level="info")

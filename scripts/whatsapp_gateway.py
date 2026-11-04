"""Development webhook-only forwarder; the existing API verifies/processes Meta events."""
import argparse
from urllib.parse import urlparse
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response


def create_gateway(api_url='http://127.0.0.1:8002'):
    parsed = urlparse(api_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1') or parsed.username or parsed.password:
        raise ValueError('Gateway target must be a local HTTP API')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route('/api/v1/webhooks/whatsapp', methods=['GET', 'POST'])
    async def webhook(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1048576:
                raise HTTPException(413, 'Webhook too large')
        headers = {k: v for k, v in request.headers.items() if k.lower() in ('content-type', 'x-hub-signature-256')}
        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
                response = await client.request(request.method, api_url.rstrip('/')+'/api/v1/webhooks/whatsapp',
                                                params=request.query_params, content=bytes(body), headers=headers)
        except httpx.HTTPError:
            # Never include URLs: the GET query contains the verification token.
            raise HTTPException(502, 'Local webhook API unavailable') from None
        return Response(response.content, status_code=response.status_code,
                        headers={'content-type': response.headers.get('content-type', 'text/plain')})
    return app


if __name__ == '__main__':
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-url', default='http://127.0.0.1:8002')
    parser.add_argument('--port', type=int, default=8003)
    args = parser.parse_args()
    uvicorn.run(create_gateway(args.api_url), host='127.0.0.1', port=args.port, access_log=False)

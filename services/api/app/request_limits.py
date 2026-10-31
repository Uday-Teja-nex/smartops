"""Bound request bodies before routing or database side effects."""
from starlette.responses import JSONResponse


class RequestSizeLimit:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        lengths = [value for name, value in scope.get('headers', []) if name.lower() == b'content-length']
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit():
                return await JSONResponse({'detail': 'Invalid Content-Length'}, status_code=400)(scope, receive, send)
            if len(lengths[0]) > 20 or int(lengths[0]) > self.max_bytes:
                return await self.reject(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body) + len(chunk) > self.max_bytes:
                return await self.reject(scope, receive, send)
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, replay, send)

    async def reject(self, scope, receive, send):
        await JSONResponse({'detail': 'Request body exceeds the size limit'}, status_code=413)(scope, receive, send)

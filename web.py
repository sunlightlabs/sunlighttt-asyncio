import asyncio
import json
import os
from aiohttp import web
from functools import wraps

import triggers

PORT = os.environ.get('PORT', '8000')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '')


@asyncio.coroutine
def data_middleware(app, handler):
    @asyncio.coroutine
    def middleware(request):
        try:
            request.data = yield from request.json()
        except ValueError:
            request.data = {}
        return (yield from handler(request))
    return middleware


@asyncio.coroutine
def auth_middleware(app, handler):
    @asyncio.coroutine
    def middleware(request):

        key = request.headers.get('IFTTT-Channel-Key', '')
        if key == CLIENT_SECRET:
            return (yield from handler(request))

        msg = {
            "errors": [
                {"message": "Unauthorized. Always gotta be sneaking about, eh?"}
            ]
        }
        raise web.HTTPUnauthorized(
            text=json.dumps(msg), content_type='application/json')

    return middleware


@asyncio.coroutine
def status(request):
    return web.Response(body=b"Hello, world")


@asyncio.coroutine
def test_setup(request):
    return web.Response(body=b"Hello, world")


@asyncio.coroutine
def trigger(request):

    name = request.match_info['trigger'].replace('-', '_')
    handler = getattr(triggers, name, None)

    if not handler:
        msg = 'No such trigger: {}'.format(name)
        raise web.HTTPInternalServerError(text=msg)

    before = request.data.get('before')
    after = request.data.get('after')
    limit = request.data.get('limit')

    if limit == 0:
        return web.Response(text=json.dumps({"data": []}),
                            content_type='application/json')

    resp = yield from handler.check(None, before, after, limit)
    return resp


@asyncio.coroutine
def options(request):
    return web.Response(body=b"Hello, world")


@asyncio.coroutine
def validate(request):
    return web.Response(body=b"Hello, world")


app = web.Application(middlewares=[auth_middleware, data_middleware])
app.router.add_route(
    'GET', '/ifttt/v1/status', status)
app.router.add_route(
    'POST', '/ifttt/v1/test/setup', test_setup)
app.router.add_route(
    'POST', '/ifttt/v1/triggers/{trigger}', trigger)
app.router.add_route(
    'POST', '/ifttt/v1/triggers/{trigger}/fields/{field}/options', options)
app.router.add_route(
    'POST', '/ifttt/v1/triggers/{trigger}/fields/{field}/validate', validate)


if __name__ == '__main__':

    if not CLIENT_SECRET:
        print('!!! no client secret set, not checking auth.')

    loop = asyncio.get_event_loop()
    f = loop.create_server(app.make_handler(), '0.0.0.0', PORT)
    srv = loop.run_until_complete(f)

    print('serving on', srv.sockets[0].getsockname())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

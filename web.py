import asyncio
import datetime
import json
import os
import re
import aiohttp
# import aiomcache
from aiohttp import web
from functools import wraps

import triggers
from util import JSONResponse, ErrorResponse

CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '')

STATUS_URL = 'https://congress.api.sunlightfoundation.com'


# cache = aiomcache.Client("127.0.0.1", 11211)


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
        if key == CLIENT_SECRET or not CLIENT_SECRET:
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
    resp = yield from aiohttp.request('get', STATUS_URL)

    if resp.status == 200:
        msg = "We just checked our Congress API's status and it's fine."
    else:
        msg = "Our API seems unavailable right now."

    data = {
        "status": "OK" if resp.status == 200 else  "UNAVAILABLE",
        "time": datetime.date.today().isoformat(),
        "message": msg,
    }
    return JSONResponse(data)


@asyncio.coroutine
def test_setup(request):
    data = {
        "samples": {
            "triggers": {
                "new-bills-query": {
                    "query": "\"Common Core\""
                },
                "new-legislators": {
                    "location": {
                        "lat": 44.967586,
                        "lng": -103.772234,
                        "address": "19424 Us Highway 85, Belle Fourche, SD 57717",
                        "description": "Geographic Center of the United States"
                    }
                }
            }
        }
    }
    return JSONResponse(data)


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
        return JSONResponse([])

    trigger_fields = request.data.get('triggerFields') or {}

    if handler.fields:
        if not trigger_fields:
            return ErrorResponse('triggerFields is required')
            for field in handler.fields:
                val = trigger_fields.get(field)
                if handler.fields[field].required and not val:
                    return ErrorResponse('{} field is required'.format(field))

    # dstr = json.dumps(trigger_fields, sort_keys=True)
    # dstr = re.sub(r'[^a-zA-Z0-9]', '', dstr)
    # key = '{}:{}'.format(name, dstr)

    resp = yield from handler.check(trigger_fields, before, after, limit)
    return resp


@asyncio.coroutine
def options(request):
    return web.Response(body=b"Hello, world")


@asyncio.coroutine
def validate(request):

    name = request.match_info['trigger'].replace('-', '_')
    field = request.match_info['field']

    handler = getattr(triggers, name, None)

    if not handler:
        msg = 'No such trigger: {}'.format(name)
        raise web.HTTPInternalServerError(text=msg)

    if handler.fields and field in handler.fields:

        val = request.data.get('value')
        result = handler.fields[field].validate(val)

        data = {'valid': result == True}
        if result != True:
            data['message'] = result

    else:
        data = {
            'valid': False,
            'message': 'No such field: {}'.format(field),
        }

    return web.Response(text=json.dumps({'data': data}),
                        content_type='application/json')


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

    PORT = os.environ.get('PORT', '8000')

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

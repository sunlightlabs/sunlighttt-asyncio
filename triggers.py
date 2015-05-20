import asyncio
import json
import os
import aiohttp
from aiohttp import web

SUNLIGHT_KEY = os.environ.get('SUNLIGHT_KEY')
SUNLIGHT_URL = 'https://congress.api.sunlightfoundation.com'


class Trigger(object):

    @asyncio.coroutine
    def check(self, fields, before, after, limit):
        raise NotImplemented()

    @property
    def fields(self):
        return {}


class UpcomingBillsTrigger(Trigger):

    fields = None

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        url = '{}/{}'.format(SUNLIGHT_URL, 'upcoming_bills')
        params = {
            'fields': ','.join(["bill_id", "chamber", "legislative_day",
                       "range", "url", "bill", "scheduled_at"]),
            'range__exists': 'true',
            'order': 'scheduled_at',
        }

        if limit:
            params['per_page'] = limit

        headers = {'X-APIKEY': SUNLIGHT_KEY}

        resp = yield from aiohttp.request('get', url,
                                          params=params, headers=headers)
        data = yield from resp.json()

        ifttt = []

        for upcoming_bill in data['results']:

            # meta: {
            #     "id": upcoming_bill.range + "/" + upcoming_bill.legislative_day + "/" + upcoming_bill.bill_id,
            #     "timestamp": timestamp
            #   },

            #   Code: Sunlight.billCode(Sunlight.parseBillId(upcoming_bill.bill_id)),
            #   Title: bill ? Sunlight.billTitle(bill) : "(Not yet known)",
            #   SponsorName: bill ? Sunlight.name(bill.sponsor) : "(Not yet known)",
            #   LegislativeDate: dateDisplay,
            #   Chamber: Sunlight.chamberName(upcoming_bill.chamber),
            #   SourceURL: upcoming_bill.url,
            #   date: upcoming_bill.legislative_day

            record = {
                'meta': {
                    'id': 0,
                    'timestamp': 0,
                },
                'Code': '',
                'Title': '',
                'SponsorName': '',
                'LegislativeDate': '',
                'Chamber': upcoming_bill['chamber'],
                'SourceURL': upcoming_bill['url'],
                'date': upcoming_bill['legislative_day'],
            }
            ifttt.append(record)

        return web.Response(text=json.dumps({'data': ifttt}),
                            content_type='application/json')


upcoming_bills = UpcomingBillsTrigger()

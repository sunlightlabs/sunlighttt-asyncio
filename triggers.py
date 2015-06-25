import asyncio
import datetime
import json
import os
import aiohttp
from aiohttp import web
from dateutil.parser import parse
from operator import itemgetter

import util
from fields import PointField, QueryField

SUNLIGHT_KEY = os.environ.get('SUNLIGHT_KEY')
SUNLIGHT_URL = 'https://congress.api.sunlightfoundation.com'


class Trigger(object):

    fields = None

    @property
    def fields(self):
        return {}

    def cache_key(self, request):
        key = request.path
        limit = request.data.get('limit')
        if limit:
            key = '{}:limit={}'.format(key, limit)
        return key

    @asyncio.coroutine
    def check(self, fields, before, after, limit):
        raise NotImplemented()

    @asyncio.coroutine
    def get_json(self, url, params=None, headers=None, limit=None):

        if not params:
            params = {}

        if limit:
            params['per_page'] = limit

        if not headers:
            headers = {}
        headers.update({'X-APIKEY': SUNLIGHT_KEY})

        resp = yield from aiohttp.request(
            'get', url, params=params, headers=headers)
        data = yield from resp.json()
        return data


class CongressBirthdays(Trigger):

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        today = datetime.datetime.utcnow() - datetime.timedelta(hours=13)
        # today = today.replace(hour=0, minute=0, second=0)
        today = today.date()

        url = '{}/{}'.format(SUNLIGHT_URL, 'legislators')
        params = {
            'fields': ','.join(
                ["title", "first_name", "last_name", "state", "party",
                 "district", "birthday", "bioguide_id", "twitter_id"]),
            'per_page': 'all',
        }

        data = yield from self.get_json(url, params=params)

        legislators = []

        for legislator in data['results']:

            bday = parse(legislator['birthday'])
            bday = bday.replace(year=today.year, hour=0, minute=0, second=0)

            legislator['current_birthday'] = bday

            bday = bday.date()

            is_good = bday <= today

            if is_good and before:
                is_good = is_good and bday <= util.epoch_to_date(before)

            if is_good and after:
                is_good = is_good and bday > util.epoch_to_date(after)

            if is_good:
                legislators.append(legislator)

        legislators = sorted(legislators, key=itemgetter('last_name'))
        legislators = sorted(legislators,
                             key=itemgetter('current_birthday'),
                             reverse=True)

        ifttt = []

        for legislator in legislators:

            birth_year = parse(legislator['birthday']).year

            record = {
                'meta': {
                    'id': '{}/{}'.format(today.year, legislator['bioguide_id']),
                    'timestamp': int(legislator['current_birthday'].timestamp()),
                },
                'name': '{title}. {first_name} {last_name}'.format(**legislator),
                'state': '{state}-{district}'.format(**legislator) \
                    if legislator.get('district') else legislator['state'],
                'party': legislator['party'],
                'twitter_username': legislator.get('twitter_id') or '',
                'birthday_date': util.readable_date(legislator['birthday']),
                'numerical_birthday_date': legislator['birthday'],
                'birth_year': birth_year,
                'age': today.year - birth_year,
                'date': legislator['current_birthday'].date().isoformat(),
            }
            ifttt.append(record)

        return util.JSONResponse(ifttt[:limit or 20])


class NewBillsQuery(Trigger):

    fields = {
        'query': QueryField()
    }

    def cache_key(self, request):
        key = super(NewBillsQuery, self).cache_key(request)
        fields = request.data.get('triggerFields')
        query = fields.get('query')
        return '{}:query={}'.format(key, query)

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        url = '{}/{}'.format(SUNLIGHT_URL, 'bills/search')
        params = {
            'fields': ','.join(
                ["bill_id", "bill_type", "number", "introduced_on",
                 "short_title", "official_title", "sponsor",
                 "urls.congress", "urls.opencongress"]),
            'query': fields.get('query'),
            'order': 'congress,introduced_on,number',
        }

        data = yield from self.get_json(url, params=params, limit=limit)

        if before:
            params['introduced_on__lte'] = util.epoch_to_date(before)
            params['order'] = 'introduced_on__desc'

        if after:
            params['introduced_on__gte'] = util.epoch_to_date(after)
            params['order'] = 'introduced_on__asc'

        ifttt = []

        for bill in data['results']:

            timestamp = util.date_to_epoch(bill['introduced_on'])

            record = {
                'meta': {
                    'id': bill['bill_id'],
                    'timestamp': timestamp,
                },
                'query': fields.get('query'),
                'sponsor_name': util.name(bill['sponsor']),
                'code': util.bill_code(bill),
                'title': util.bill_title(bill),
                'introduced_on': util.readable_date(bill['introduced_on']),
                'official_url': bill['urls']['congress'],
                'open_congress_url': bill['urls']['opencongress'],
                'date': bill['introduced_on'],
            }
            ifttt.append(record)

        return util.JSONResponse(ifttt)


class NewLawsTrigger(Trigger):

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        url = '{}/{}'.format(SUNLIGHT_URL, 'bills')
        params = {
            'fields': ','.join(
                ["bill_id", "bill_type", "number", "history.enacted_at",
                 "short_title", "official_title", "sponsor",
                 "urls.congress", "urls.opencongress"]),
            'history.enacted': 'true',
            'order': 'history.enacted_at',
        }

        if before:
            params['history.enacted_at__lte'] = util.epoch_to_date(before)
            params['order'] = 'history.enacted_at__desc'

        if after:
            params['history.enacted_at__gte'] = util.epoch_to_date(after)
            params['order'] = 'history.enacted_at__asc'

        data = yield from self.get_json(url, params=params, limit=limit)

        ifttt = []

        for bill in data['results']:

            timestamp = util.date_to_epoch(bill['history']['enacted_at'])

            record = {
                'meta': {
                    'id': bill['bill_id'],
                    'timestamp': timestamp,
                },
                'SponsorName': util.name(bill['sponsor']),
                'Code': util.bill_code(bill),
                'Title': util.bill_title(bill),
                'BecameLawOn': util.readable_date(bill['history']['enacted_at']),
                'OfficialURL': bill['urls']['congress'],
                'OpenCongressURL': bill['urls']['opencongress'],
                'date': bill['history']['enacted_at'],
            }
            ifttt.append(record)

        return util.JSONResponse(ifttt)


class NewLegislatorsTrigger(Trigger):

    fields = {
        'location': PointField()
    }

    def cache_key(self, request):
        key = super(NewLegislatorsTrigger, self).cache_key(request)
        fields = request.data.get('triggerFields')
        loc = fields.get('location')
        return '{}:ll={},{}'.format(
            key, loc['lat'], loc.get('lon') or loc.get('lng'))

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        limit = limit or 10

        loc = fields['location']

        url = '{}/{}'.format(SUNLIGHT_URL, 'legislators/locate')
        params = {
            'fields': ','.join(
                ["title", "first_name", "last_name", "bioguide_id",
                 "state", "party", "district", "terms",
                 "twitter_id", "phone", "website"]),
            'latitude': loc['lat'],
            'longitude': loc.get('lon') or loc.get('lng'),
        }

        data = yield from self.get_json(url, params=params)

        ifttt = []

        for legislator in data['results']:

            district = '{}{}'.format(
                legislator['state'], legislator.get('district') or '')

            terms = []
            for t in legislator['terms']:
                term_district = '{}{}'.format(
                    t['state'], t.get('district') or '')
                if term_district == district:
                    terms.append(t)

            term_start = terms[0]['start'];

            timestamp = util.time_to_epoch(term_start)

            record = {
                'meta': {
                    'id': '{}/{}'.format(legislator['bioguide_id'], district),
                    'timestamp': timestamp,
                },
                'name': '{title}. {first_name} {last_name}'.format(**legislator),
                'state': '{state}-{district}'.format(**legislator) \
                    if legislator.get('district') else legislator['state'],
                'party': legislator['party'],
                'phone': legislator.get('phone') or '',
                'website': legislator.get('website') or '',
                'twitter_username': legislator.get('twitter_id') or '',
                'date': term_start,
            }
            ifttt.append(record)

        ifttt = sorted(ifttt, key=lambda x: x['date'], reverse=True)

        return util.JSONResponse(ifttt[:limit])


class UpcomingBillsTrigger(Trigger):

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        url = '{}/{}'.format(SUNLIGHT_URL, 'upcoming_bills')
        params = {
            'fields': ','.join(
                ["bill_id", "chamber", "legislative_day",
                 "range", "url", "bill", "scheduled_at"]),
            'range__exists': 'true',
            'order': 'scheduled_at',
        }

        data = yield from self.get_json(url, params=params, limit=limit)

        ifttt = []

        for upcoming in data['results']:

            timestamp = util.time_to_epoch(upcoming['scheduled_at'])

            display_date = util.readable_date(upcoming['legislative_day'])
            if upcoming['range'] == 'week':
                display_date = "the week of " + display_date;

            bill = upcoming.get('bill')

            parts = util.parse_bill_id(upcoming['bill_id'])
            code = util.bill_code(parts) if parts else upcoming['bill_id'].strip()

            record = {
                'meta': {
                    'id': '{range}/{legislative_day}/{bill_id}'.format(**upcoming),
                    'timestamp': timestamp,
                },
                'Code': code,
                'Title': util.bill_title(bill) if bill else "(Not yet known)",
                'SponsorName': util.name(bill['sponsor']) if bill else "(Not yet known)",
                'LegislativeDate': display_date,
                'Chamber': util.chamber_name(upcoming['chamber']),
                'SourceURL': upcoming['url'],
                'date': upcoming['legislative_day'],
            }
            ifttt.append(record)

        return util.JSONResponse(ifttt)


congress_birthdays = CongressBirthdays()
new_bills_query = NewBillsQuery()
new_laws = NewLawsTrigger()
new_legislators = NewLegislatorsTrigger()
upcoming_bills = UpcomingBillsTrigger()

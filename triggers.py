import asyncio
import datetime
import os
import aiohttp
from dateutil.parser import parse
from operator import itemgetter

import util
from fields import PointField, QueryField

PROPUBLICA_KEY = os.environ.get('PROPUBLICA_KEY')
PROPUBLICA_URL = 'https://api.propublica.org/congress/v1'


class Trigger(object):

    fields = None

    @property
    def fields(self):
        return {}

    def cache_key(self, request):
        key = request.path
        limit = request.data.get('limit')
        if limit is not None:
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
        headers.update({'X-API-Key': PROPUBLICA_KEY})

        resp = yield from aiohttp.request(
            'get', url, params=params, headers=headers)
        data = yield from resp.json()
        return data


# TODO
class CongressBirthdays(Trigger):

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        today = datetime.datetime.utcnow() - datetime.timedelta(hours=13)
        # today = today.replace(hour=0, minute=0, second=0)
        today = today.date()

        url = '{}/{}'.format(PROPUBLICA_URL, 'legislators')
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
                'state': '{state}-{district}'.format(**legislator)
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


# TODO
class NewBillsQuery(Trigger):

    fields = {
        'query': QueryField()
    }

    def cache_key(self, request):
        key = super(NewBillsQuery, self).cache_key(request)
        fields = request.data.get('triggerFields')
        if fields:
            query = fields.get('query')
            key = '{}:query={}'.format(key, query)
        return key

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        url = '{}/{}'.format(PROPUBLICA_URL, 'bills/search')
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


# TODO
class NewLawsTrigger(Trigger):

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        url = '{}/{}'.format(PROPUBLICA_URL, 'bills')
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
                'OpenCongressURL': bill['urls']['congress'],
                'date': bill['history']['enacted_at'],
            }
            ifttt.append(record)

        return util.JSONResponse(ifttt)


# TODO
class NewLegislatorsTrigger(Trigger):

    fields = {
        'location': PointField()
    }

    def cache_key(self, request):
        key = super(NewLegislatorsTrigger, self).cache_key(request)
        fields = request.data.get('triggerFields')
        if fields:
            loc = fields.get('location')
            if loc:
                key = '{}:ll={},{}'.format(
                    key, loc['lat'], loc.get('lon') or loc.get('lng'))
        return key

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        limit = limit or 10

        # loc = fields['location']
        #
        # #
        # #
        # # DO GEO LOC TO DISTRICT CONVERSION!
        # state = loc.state
        # district = loc.district
        #
        #
        #

        state = 'MD'

        url = '{}/{}'.format(PROPUBLICA_URL, 'members/new.json')
        resp = yield from self.get_json(url)
        data = resp['results'][0]['members']

        ifttt = []

        for legislator in data:

            if legislator['state'] == state:

                print(legislator)

            # if legislator['chamber'] == 'Senate' and legislator['state']:
            #     pass
            #
            # if legislator['chamber'] == 'House' and legislator['state'] == state and legislator['district'] == district:
            #     pass

                district = '{}{}'.format(
                    legislator['state'], legislator.get('district') or '')

                title = 'Sen' if legislator['chamber'] == 'Senate' else 'Rep'

                timestamp = util.time_to_epoch(legislator['start_date'])

                record = {
                    'meta': {
                        'id': '{}/{}'.format(legislator['id'], district),
                        'timestamp': timestamp,
                    },
                    'name': '{title}. {first_name} {last_name}'.format(title=title, **legislator),
                    'state': '{state}-{district}'.format(**legislator)
                             if legislator.get('district') else legislator['state'],
                    'party': legislator['party'],
                    'phone': legislator.get('phone') or '',
                    'website': legislator.get('website') or '',
                    'twitter_username': legislator.get('twitter_id') or '',
                    'date': legislator['start_date'],
                }
                ifttt.append(record)

        return util.JSONResponse(ifttt[:limit])


class UpcomingBillsTrigger(Trigger):

    @asyncio.coroutine
    def check(self, fields, before, after, limit):

        results = []

        for chamber in ('house', 'senate'):
            url = '{}/{}'.format(PROPUBLICA_URL, 'bills/upcoming/{}.json'.format(chamber))
            data = yield from self.get_json(url)
            print(data)
            for day in data['results']:
                results.extend(day['bills'])

        ifttt = []

        for upcoming in results:

            timestamp = util.time_to_epoch(upcoming['scheduled_at'])

            display_date = util.readable_date(upcoming['legislative_day'])
            if upcoming['range'] == 'week':
                display_date = "the week of " + display_date

            resp = yield from self.get_json(upcoming['api_uri'])
            bill_data = resp['results'][0]

            record = {
                'meta': {
                    'id': '{range}/{legislative_day}/{bill_id}'.format(**upcoming),
                    'timestamp': timestamp,
                },
                'Code': upcoming['bill_number'],
                'Title': util.bill_title(bill_data),
                'SponsorName': '{} {}'.format(bill_data['sponsor_title'], bill_data['sponsor']),
                'LegislativeDate': display_date,
                'Chamber': upcoming['chamber'].title(),
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

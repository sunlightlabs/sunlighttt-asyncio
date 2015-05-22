import datetime
import json
import re

from aiohttp import web
from dateutil.parser import parse


class JSONResponse(web.Response):
    def __init__(self, data, **kwargs):
        super(JSONResponse, self).__init__(text=json.dumps({'data': data}),
                                           content_type='application/json',
                                           **kwargs)


class ErrorResponse(web.HTTPBadRequest):
    def __init__(self, message, *args, **kwargs):
        payload = {'errors': [{'message': message}]}
        super(ErrorResponse, self).__init__(text=json.dumps(payload),
                                            content_type='application/json',
                                            **kwargs)


def validate_query(query):

    query = re.sub(r'" *~', '"~', query)
    query = re.sub(r'~ *', '~', query)

    parts = query.split('"')

    if parts[0] == '':
        parts = parts[1:]

    in_phrase = False

    for part in parts:

        in_phrase = not in_phrase

        if '*' in part and in_phrase:
            raise ValueError(
                '* is not allowed in a phrase ({})'.format(part))
        elif part[0] == '~' and re.replace(r'^~[0-9]+', '', part) == part:
            raise ValueError(
                '~ must be followed by a number after a phrase ({})'.format(part))

    return query


def bill_code(bill):
    types = {
        "hr": "H.R.",
        "hres": "H.Res.",
        "hjres": "H.J.Res.",
        "hconres": "H.Con.Res.",
        "s": "S.",
        "sres": "S.Res.",
        "sjres": "S.J.Res.",
        "sconres": "S.Con.Res."
    }
    return '{} {}'.format(types[bill['bill_type']], bill['number'])


def bill_title(bill):
    return bill.get('short_title') or bill.get('official_title')


def chamber_name(chamber):
    names = {
        "house": "House of Representatives",
        "senate": "Senate",
    }
    return names.get(chamber) or ''


def name(person):
    first = person.get('nickname') or person.get('first_name')
    last = '{} {}'.format(person['last_name'], person.get('suffix') or '').strip()
    return '{}. {} {}'.format(person['title'], first, last)


def parse_bill_id(bill_id):
    parts = re.match(r'([cehjnors]+)(\d+)-(\d+)', bill_id.lower()).groups()
    return {
        'bill_type': parts[0],
        'number': parts[1],
        'session': parts[2],
    }


def date_to_epoch(dstr):

    # Format a date stamp (YYYY-MM-DD) into a Unix epoch time.
    #
    # The Congress API (and Congress) work on EST. For example,
    # 2014-01-24 should be treated as 2014-01-24 00:00:00 EST,
    # and thus converted to: 1390539600.
    #
    # IFTTT epochs need to be in seconds, JS uses milliseconds.

    dt = parse(dstr).replace(hour=0, minute=0, second=0)
    return int(dt.timestamp())


def time_to_epoch(tstr):
    dt = parse(tstr)
    return int(dt.timestamp())


def readable_date(ymd):

    months = ["January", "February", "March", "April", "May",
              "June", "July", "August", "September", "October",
              "November", "December"]

    dt = parse(ymd)
    mon = dt.month
    dom = dt.day

    if dom == 1 or dom == 21 or dom == 31:
        suffix = 'st'
    elif dom == 2 or dom == 22:
        suffix = 'nd'
    elif dom == 3 or dom == 23:
        suffix = 'rd'
    else:
        suffix = 'th'

    return '{} {}{}, {}'.format(months[mon - 1], dom, suffix, dt.year)


def epoch_to_date(epoch):

    # Format a Unix epoch time into a date stamp (YYYY-MM-DD).
    #
    # The Congress API (and Congress) work on EST. For example,
    # only convert to 2014-01-24 if the Unix timestamp is between
    #
    # 2014-01-24 00:00:00 EST   and   2014-01-24 23:59:59 EST.
    #       1390539600          and         1390582799

    dt = datetime.date.fromtimestamp(epoch)
    return dt.strftime('%Y-%m-%d')

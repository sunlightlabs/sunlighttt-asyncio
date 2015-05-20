import re


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
    last = '{} {}'.format(person['last_name'], person.get('suffix') or '').trim()
    return '{}. {} {}'.format(person['title'], first, last)


def parse_bill_id(bill_id):
    parts = re.match(r'([cehjnors]+)(\d+)-(\d+)', bill_id.lower()).groups()
    return {
        'bill_type': parts[1],
        'number': parts[2],
        'session': parts[3],
    }


"""
  // Format a date stamp (YYYY-MM-DD) into a Unix epoch time.
  //
  // The Congress API (and Congress) work on EST. For example,
  // 2014-01-24 should be treated as 2014-01-24 00:00:00 EST,
  // and thus converted to: 1390539600.
  //
  // IFTTT epochs need to be in seconds, JS uses milliseconds.
  dateToEpoch: function(date, timezone) {
    if (!timezone) timezone = "America/New_York";

    var date = new time.Date(date + " 00:00:00", timezone);
    return date.getTime() / 1000;
  },

  // assumes a fully timezone-qualified timestamp
  timeToEpoch: function(timestamp) {
    var date = new time.Date(timestamp);
    return parseInt(date.getTime() / 1000);
  },

  /**
    Content helper functions
  **/

  // display name for a member of Congress

  readableDate: function(ymd) {
    var months = ["January", "February", "March", "April", "May",
                  "June", "July", "August", "September", "October",
                  "November", "December"];

    var d = new Date(Sunlight.dateToEpoch(ymd) * 1000),
        dom = d.getDate(),
        s = months[d.getMonth()] + " " + dom;

    if (dom === 1 || dom === 21 || dom === 31) {
      s += "st";
    } else if (dom === 2 || dom === 22) {
      s += "nd";
    } else if (dom === 3 || dom === 23) {
      s += "rd";
    } else {
      s += "th";
    }

    year = d.getFullYear();

    return s + ", " + year;
  },

};
"""
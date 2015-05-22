import util


class Field(object):

    required = True

    def validate(self, val):
        pass


class PointField(Field):
    def validate(self, val):
        return True


class QueryField(Field):
    def validate(self, val):
        msg = "query is required"
        is_valid = (val or '').strip() != ''
        try:
            util.validate_query(val)
        except ValueError as ve:
            msg = str(ve)
            is_valid = False
        return True if is_valid else msg

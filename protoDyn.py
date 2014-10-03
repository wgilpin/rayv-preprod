__author__ = 'Will'


class protoDyn():
    _fields = {}
    _fieldOrder = []
    _values = {}

    def __init__(self, schema):
        self._fieldOrder = [None] * (len(schema) + 1)
        for field in schema:
            required = field['required'] if 'required' in field else True
            seq_no = field['no']
            self._fields[field['name']] = {"required": required,
                                           "no": seq_no}
            self._fieldOrder[field['no']] = field['name']
        self._values = {}

    def __getitem__(self, item):
        if item in self._fields:
            return self._values[item]
        raise AttributeError, item

    def __setitem__(self, key, value):
        if key in self._fields:
            self._values[key] = value
        else:
            raise AttributeError, key

    def validate(self):
        valid = True
        results = []
        for field_name in self._fields:
            required = self._fields[field_name]['required']
            if required:
                if field_name in self._values:
                    if not self._values[field_name]:
                        valid = False
                        results.append("%s has value None" % field_name)
                else:
                    valid = False
                    results.append("%s is not set" % field_name)
        return valid, results

    def open_webapp2_request(self, request):
        valid = True
        results = []
        for field_name in self._fields:
            required = self._fields[field_name]['required']
            if required:
                if field_name in self._fields:
                    if field_name in request.params:
                        if not request.params[field_name]:
                            valid = False
                            results.append("%s has value None" % field_name)
                    else:
                        valid = False
                        results.append("%s is not set" % field_name)
                else:
                    valid = False
                    results.append("%s is not a field" % field_name)
            if valid or not required:
                self._values[field_name] = request.params[field_name]
        return valid



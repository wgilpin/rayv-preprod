from unittest import TestCase
from protoDyn import protoDyn

__author__ = 'Will'

testProto = [
    {"name": "field1",
     "required": True,
     "no": 1},
    {"name": "field2",
     "required": False,
     "no": 2},
    {"name": "field3",
     "no": 3},
]


class TestProtoDyn(TestCase):
    def test_validate_all_present(self):
        proto = protoDyn(testProto)
        proto['field1'] = "value1"
        proto['field2'] = "value2"
        proto['field3'] = "value3"
        valid, errors = proto.validate()
        self.assertEqual(valid, True, "Should be valid")
        self.assertEqual(errors, [], "Should be no errors")

    def test_validate_missing_required(self):
        proto = protoDyn(testProto)
        proto['field1'] = "value1"
        proto['field2'] = "value2"
        valid, errors = proto.validate()
        self.assertEqual(valid, False, "Should be invalid")
        self.assertNotEqual(errors, [], "Should be errors")

    def test_validate_missing_optional(self):
        proto = protoDyn(testProto)
        proto['field1'] = "value1"
        proto['field3'] = "value3"
        valid, errors = proto.validate()
        self.assertEqual(valid, True, "Should be valid")
        self.assertEqual(errors, [], "Should be no errors")

    def test_invalid_field(self):
        proto = protoDyn(testProto)
        try:
            proto['field4'] = "value1"
            self.fail("field4 is not a field")
        except AttributeError:
            pass

    def test_open_webapp2_request(self):
        class FakeRequest():
            params = None

            def __init__(self, params):
                self.params = params


        request = FakeRequest({
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        })
        proto = protoDyn(testProto)
        self.assertTrue(proto.open_webapp2_request(request), "failed to validate")
        self.assertEqual(proto['field1'], 'value1')
        self.assertEqual(proto['field2'], 'value2')
        self.assertEqual(proto['field3'], 'value3')

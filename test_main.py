__author__ = 'Will'

from google import appengine
from google.appengine.ext import testbed
from google.appengine.ext import ndb

import unittest

class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.tb = testbed.Testbed()
        self.tb.setup_env()
        self.tb.activate()
        self.tb.init_datastore_v3_stub()

    def tearDown(self):
        self.tb.deactivate()

if __name__ == '__main__':
    unittest.main()
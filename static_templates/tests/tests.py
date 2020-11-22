from django.test import TestCase
from django.conf import settings
import logging


# Create your tests here.
class NominalTestCase(TestCase):
    logger = logging.getLogger(__name__ + '.UpdateSetTestCase')

    def setUp(self):
        pass

    def test_generate(self):
        self.logger.info('running ' + self.test_generate.__name__)
        self.assertEqual(0, 0)

#class SignalTestCase(TestCase):
#    logger = logging.getLogger(__name__ + '.SignalTestCase')

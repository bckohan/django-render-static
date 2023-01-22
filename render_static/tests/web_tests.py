"""
Single Page Application (SPA) tests. These tests test several patterns that
allow apps using urls_to_js to be included more than once and under different
namespaces. These patterns incur a dependency on renderstatic to any
users of the SPA apps. See Runtimes in the documentation for more details.
"""
import json
import os

from django.core.management import call_command
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from render_static.tests.tests import LOCAL_STATIC_DIR, BaseTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import shutil

chrome_options = Options()
chrome_options.add_argument("--headless")
driver = webdriver.Chrome(shutil.which('chromedriver'), options=chrome_options)


@override_settings(
    INSTALLED_APPS=[
        'render_static.tests.spa',
        'render_static',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.admin'
    ],
    ROOT_URLCONF='render_static.tests.spa_urls',
    STATICFILES_DIRS=[
        ('spa', LOCAL_STATIC_DIR),
    ],
    STATIC_TEMPLATES={
        'templates': {
            'spa/urls.js': {
                'context': {
                    'include': ['spa1', 'spa2']
                },
                'dest': str(LOCAL_STATIC_DIR / 'urls.js')
            }
        }
    }
)
class TestMultipleURLTreeSPAExample(BaseTestCase, LiveServerTestCase):

    def setUp(self):
        os.makedirs(LOCAL_STATIC_DIR, exist_ok=True)
        call_command('renderstatic', 'spa/urls.js', '--traceback')
        call_command('collectstatic')

    def test_example_pattern(self):
        driver.get(f'{self.live_server_url}{reverse("spa1:index")}')
        from pprint import pprint
        pprint(driver.get_log("browser"))
        elem = driver.find_element(By.ID, 'qry-result')
        self.assertEqual(json.loads(elem.text)['request'], '/spa1/qry/')
        elem = driver.find_element(By.ID, 'qry-result-arg')
        self.assertEqual(json.loads(elem.text)['request'], '/spa1/qry/5')

        driver.get(f'{self.live_server_url}{reverse("spa2:index")}')
        elem = driver.find_element(By.ID, 'qry-result')
        self.assertEqual(json.loads(elem.text)['request'], '/spa2/qry/')
        elem = driver.find_element(By.ID, 'qry-result-arg')
        self.assertEqual(json.loads(elem.text)['request'], '/spa2/qry/5')

    # def tearDown(self):
    #     pass

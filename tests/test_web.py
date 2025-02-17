"""
Single Page Application (SPA) tests. These tests test several patterns that
allow apps using urls_to_js to be included more than once and under different
namespaces. These patterns incur a dependency on renderstatic to any
users of the SPA apps. See Runtimes in the documentation for more details.
"""

import json
import logging
import os

import time
from django.core.management import call_command
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from selenium.webdriver.common.by import By
from contextlib import contextmanager

from tests.test_core import LOCAL_STATIC_DIR, BaseTestCase

logger = logging.getLogger(__name__)


@contextmanager
def web_driver(width=1920, height=1200):
    import platform
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions

    # Set up headless browser options
    def opts(options=ChromeOptions()):
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={width}x{height}")
        return options

    def chrome():
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=opts()
        )

    def chromium():
        from selenium.webdriver.chrome.service import Service as ChromiumService
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import ChromeType

        return webdriver.Chrome(
            service=ChromiumService(
                ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
            ),
            options=opts(),
        )

    def firefox():
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager

        return webdriver.Firefox(
            service=FirefoxService(GeckoDriverManager().install()),
            options=opts(Options()),
        )

    def edge():
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager

        options = Options()
        options.use_chromium = True
        return webdriver.Edge(
            service=EdgeService(EdgeChromiumDriverManager().install()),
            options=opts(options),
        )

    services = [
        chrome,
        edge if platform.system().lower() == "windows" else chromium,
        firefox,
    ]

    driver = None
    for service in services:
        try:
            driver = service()
            break  # use the first one that works!
        except Exception as err:
            pass

    if driver:
        yield driver
        driver.quit()
    else:
        raise RuntimeError("Unable to initialize any webdriver.")


@override_settings(
    INSTALLED_APPS=[
        "tests.spa",
        "render_static",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.sites",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "django.contrib.admin",
    ],
    ROOT_URLCONF="tests.spa_urls",
    STATICFILES_DIRS=[
        ("spa", LOCAL_STATIC_DIR),
    ],
    STATIC_TEMPLATES={
        "templates": {
            "spa/urls.js": {
                "context": {"include": ["spa1", "spa2"]},
                "dest": str(LOCAL_STATIC_DIR / "urls.js"),
            }
        }
    },
)
class TestMultipleURLTreeSPAExample(BaseTestCase, LiveServerTestCase):
    def setUp(self):
        os.makedirs(LOCAL_STATIC_DIR, exist_ok=True)
        call_command("renderstatic", "spa/urls.js", "--traceback")
        call_command("collectstatic")

    def test_example_pattern(self):
        with web_driver() as driver:
            driver.get(f"{self.live_server_url}{reverse('spa1:index')}")
            time.sleep(2)
            elem = driver.find_element(By.ID, "qry-result")
            text = str(elem.text)
            js = json.loads(text)
            self.assertEqual(js["request"], "/spa1/qry/")
            elem = driver.find_element(By.ID, "qry-result-arg")
            text = str(elem.text)
            js = json.loads(text)
            self.assertEqual(js["request"], "/spa1/qry/5")

            driver.get(f"{self.live_server_url}{reverse('spa2:index')}")
            time.sleep(2)
            elem = driver.find_element(By.ID, "qry-result")
            text = str(elem.text)
            js = json.loads(text)
            self.assertEqual(js["request"], "/spa2/qry/")
            elem = driver.find_element(By.ID, "qry-result-arg")
            text = str(elem.text)
            js = json.loads(text)
            self.assertEqual(js["request"], "/spa2/qry/5")

    # def tearDown(self):
    #     pass

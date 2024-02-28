try:
    # weird issue where cant just import jinja2 b/c leftover __pycache__
    # allows it to "import"
    from jinja2 import environment

    from render_static.tests._jinja2_tests import *
except ImportError:
    pass

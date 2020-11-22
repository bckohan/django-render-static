from django import template
import json

register = template.Library()


@register.filter(name='convert_to_js_defines')
def convert_to_js_defines(modules, indent=''):
    import inspect
    js = ''
    classes = {}
    for module in modules:
        for key in dir(module):
            cls = getattr(module, key)
            if inspect.isclass(cls):
                classes[cls] = {n: getattr(cls, n) for n in dir(cls) if n.isupper()}

    first = True
    for cls, dfs in classes.items():
        if len(dfs) > 0:
            js += '%s%s: { \n' % (indent if not first else '', cls.__name__)
            first = False

            for a in cls.__mro__:
                if a != cls and a in classes:
                    idx = 1
                    for key, val in classes[a].items():
                        js += '%s     %s: %s,\n' % (indent, key, json.dumps(val))
                        idx += 1

            idx = 1
            for key, val in dfs.items():
                js += '%s     %s: %s%s\n' % (indent, key, json.dumps(val), ',' if idx < len(dfs) else '')
                idx += 1

            js += '%s},\n\n' % (indent,)

    return js


@register.filter(name='js_variable')
def js_variable(object):
    if isinstance(object, bool):
        return 'true' if object else 'false'
    try:
        float(object)
        return object
    except ValueError:
        return '"' + str(object) + '"'
    # except TypeError:
    #    import pdb
    #    pdb.set_trace()

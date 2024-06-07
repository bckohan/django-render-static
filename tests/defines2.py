class ExtDefines(object):
    EDEFINE1 = "ED1"
    EDEFINE2 = "ED2"
    EDEFINE3 = "ED3"
    EDEFINES = (
        (EDEFINE1, "EDefine 1"),
        (EDEFINE2, "EDefine 2"),
        (EDEFINE3, "EDefine 3"),
    )


class EmptyDefines(object):
    """
    This should not show up when a module is dumped!
    """

    pass

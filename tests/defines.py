class TestDefines(object):
    DEFINE1 = "D1"
    DEFINE2 = "D2"
    DEFINE3 = "D3"
    DEFINES = (
        (DEFINE1, "Define 1"),
        (DEFINE2, "Define 2"),
        (DEFINE3, "Define 3"),
    )


class MoreDefines(object):
    MDEF1 = "MD1"
    MDEF2 = "MD2"
    MDEF3 = "MD3"
    MDEFS = [
        (MDEF1, "MDefine 1"),
        (MDEF2, "MDefine 2"),
        (MDEF3, "MDefine 3"),
    ]

    BOOL1 = True
    BOOL2 = False


class ExtendedDefines(TestDefines):
    DEFINE4 = "D4"
    DEFINES = TestDefines.DEFINES + ((DEFINE4, "Define 4"),)

    DICTIONARY = {"Key": "value", "Numeric": 0}

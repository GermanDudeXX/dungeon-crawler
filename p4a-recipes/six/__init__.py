from pythonforandroid.recipe import PythonRecipe


class SixRecipe(PythonRecipe):
    # p4a's pyjnius recipe depends on six, but p4a itself has no recipe for
    # six (it's pure Python) - normally that's fine, p4a falls back to a
    # generic "pip install into a throwaway venv shared across every arch
    # in this build" path for exactly this case. That shared venv gets
    # created once (for the first arch) and reused, not recreated, for
    # later archs; reusing it while it goes through its own internal
    # "pip install -U pip" self-upgrade left a torn install (part-24.0,
    # part-26.x pip._vendor.resolvelib) on the second arch, crashing with
    # "cannot import name 'RequirementInformation' from
    # pip._vendor.resolvelib.structs" - confirmed by the first arch
    # (arm64-v8a) sailing through the identical steps seconds earlier,
    # then armeabi-v7a hitting the corrupted shared venv. Giving six a
    # real recipe here builds it the normal per-arch way instead, so it
    # never touches that shared venv at all.
    version = '1.17.0'
    url = 'https://files.pythonhosted.org/packages/94/e7/b2c673351809dca68a0e064b6af791aa332cf192da575fd474ed7d6f16a2/six-1.17.0.tar.gz'
    depends = ['setuptools']
    site_packages_name = 'six'
    call_hostpython_via_targetpython = False


recipe = SixRecipe()

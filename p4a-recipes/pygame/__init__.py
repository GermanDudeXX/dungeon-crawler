from os.path import join

from pythonforandroid.logger import info, shprint
from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class Pygame2Recipe(CompiledComponentsPythonRecipe):
    """
    Recipe to build apps based on SDL2-based pygame.

    Local override of p4a's bundled pygame recipe, two fixes:

    1. Adds `cython` to hostpython_prerequisites. Upstream's recipe never
       sets this (unlike e.g. its own kivy recipe, which does), so
       pygame >= 2.5.2 - which ships _sdl2 as .pyx and needs Cython to run
       `setup.py build_ext` in hostpython3 - fails with "You need cython"
       even when `cython` is listed in buildozer.spec's app-level
       requirements (that builds an ARM-cross-compiled target recipe,
       useless to the host-native hostpython3 interpreter that actually
       runs setup.py).

    2. Passes -enable-arm-neon to setup.py. Without it, pygame's SIMD
       blitters are built with neither SSE2 (correctly absent - the NDK's
       arm64/armv7 clang doesn't define __SSE2__) nor NEON (needs this
       explicit opt-in flag - pygame doesn't auto-detect ARM cross-builds).
       On a real device this surfaced as `dlopen failed: cannot locate
       symbol "alphablit_alpha_sse2_argb_surf_alpha"` for pygame.display,
       draw, image, transform and other core submodules at import time,
       which crashed the app shortly after (those modules never finish
       initializing, and Game.__init__'s very first real call is
       pygame.display.set_mode()).

       setup_extra_args is also spread into PythonRecipe.install_python_package's
       final `pip install .` call, not just `setup.py build_ext` - pip doesn't
       understand -enable-arm-neon and errors out ("not a valid editable
       requirement"). install_python_package is overridden below to an exact
       copy of upstream's minus that spread, so the flag only reaches the
       setup.py invocation it's actually meant for.

    .. warning:: Some pygame functionality is still untested, and some
        dependencies like freetype, postmidi and libjpeg are currently
        not part of the build. It's usable, but not complete.
    """

    version = '2.1.0'
    url = 'https://github.com/pygame/pygame/archive/{version}.tar.gz'

    site_packages_name = 'pygame'
    name = 'pygame'

    depends = ['sdl2', 'sdl2_image', 'sdl2_mixer', 'sdl2_ttf', 'setuptools', 'jpeg', 'png']
    call_hostpython_via_targetpython = False  # Due to setuptools
    install_in_hostpython = False
    hostpython_prerequisites = ['setuptools', 'cython==0.29.36']
    setup_extra_args = ['-enable-arm-neon']

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            setup_template = open(join("buildconfig", "Setup.Android.SDL2.in")).read()
            env = self.get_recipe_env(arch)
            env['ANDROID_ROOT'] = join(self.ctx.ndk.sysroot, 'usr')

            png = self.get_recipe('png', self.ctx)
            png_lib_dir = join(png.get_build_dir(arch.arch), '.libs')
            png_inc_dir = png.get_build_dir(arch)

            jpeg = self.get_recipe('jpeg', self.ctx)
            jpeg_inc_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

            sdl_mixer_includes = ""
            sdl2_mixer_recipe = self.get_recipe('sdl2_mixer', self.ctx)
            for include_dir in sdl2_mixer_recipe.get_include_dirs(arch):
                sdl_mixer_includes += f"-I{include_dir} "

            sdl2_image_includes = ""
            sdl2_image_recipe = self.get_recipe('sdl2_image', self.ctx)
            for include_dir in sdl2_image_recipe.get_include_dirs(arch):
                sdl2_image_includes += f"-I{include_dir} "

            setup_file = setup_template.format(
                sdl_includes=(
                    " -I" + join(self.ctx.bootstrap.build_dir, 'jni', 'SDL', 'include') +
                    " -L" + join(self.ctx.bootstrap.build_dir, "libs", str(arch)) +
                    " -L" + png_lib_dir + " -L" + jpeg_lib_dir + " -L" + arch.ndk_lib_dir_versioned),
                sdl_ttf_includes="-I"+join(self.ctx.bootstrap.build_dir, 'jni', 'SDL2_ttf'),
                sdl_image_includes=sdl2_image_includes,
                sdl_mixer_includes=sdl_mixer_includes,
                jpeg_includes="-I"+jpeg_inc_dir,
                png_includes="-I"+png_inc_dir,
                freetype_includes=""
            )
            open("Setup", "w").write(setup_file)

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['USE_SDL2'] = '1'
        env["PYGAME_CROSS_COMPILE"] = "TRUE"
        env["PYGAME_ANDROID"] = "TRUE"
        return env

    def install_python_package(self, arch, name=None, env=None, is_dir=True):
        # Exact copy of PythonRecipe.install_python_package minus spreading
        # setup_extra_args into the pip call - see class docstring.
        if name is None:
            name = self.name
        if env is None:
            env = self.get_recipe_env(arch)

        info('Installing {} into site-packages'.format(self.name))

        hpenv = env.copy()
        with current_directory(self.get_build_dir(arch.arch)):
            shprint(self._host_recipe.pip, 'install', '.',
                    '--compile', '--target',
                    self.ctx.get_python_install_dir(arch.arch),
                    _env=hpenv)


recipe = Pygame2Recipe()

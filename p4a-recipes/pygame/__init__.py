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

    2. Passes -enable-arm-neon to setup.py, needed on armeabi-v7a (32-bit
       ARM doesn't auto-define PG_ENABLE_ARM_NEON the way arm64 does - see
       fix 3). setup_extra_args is also spread into
       PythonRecipe.install_python_package's final `pip install .` call,
       not just `setup.py build_ext` - pip doesn't understand
       -enable-arm-neon and errors out ("not a valid editable
       requirement"). install_python_package is overridden below to an
       exact copy of upstream's minus that spread, so the flag only
       reaches the setup.py invocation it's actually meant for.

    3. The actual root cause of a real device crash (confirmed by pulling
       the built surface.so off a real phone via `adb shell run-as` and
       inspecting its ELF symbol table): this recipe builds pygame via a
       legacy distutils "Setup" file (see prebuild_arch below), generated
       from pygame's own buildconfig/Setup.Android.SDL2.in template. That
       template lists the `surface` module's sources as exactly
       `src_c/surface.c src_c/alphablit.c src_c/surface_fill.c` - it
       predates pygame's SIMD blitter file, src_c/simd_blitters_sse2.c,
       and was never updated to include it. alphablit.c calls SIMD blit
       functions like alphablit_alpha_sse2_argb_surf_alpha (declared in
       simd_blitters.h, which alphablit.c includes) but since
       simd_blitters_sse2.c - the file that actually *defines* them - is
       never compiled at all, they end up permanently undefined in
       surface.so, regardless of any SSE2/NEON compiler flag or macro.
       That's an unconditional dlopen-time relocation failure (the
       functions are called through a dispatch table, not a lazily-bound
       plain call site), so it crashes on every launch on every device,
       arm64 or armv7, no exceptions to catch on the Python side - this
       is what NEON alone (fix 2) could never have fixed. prebuild_arch
       patches the Setup-file text to add the missing source file to the
       surface module's line before it's written out.

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
            missing_simd_source = "src_c/simd_blitters_sse2.c"
            surface_sources = "src_c/surface.c src_c/alphablit.c src_c/surface_fill.c"
            if missing_simd_source not in setup_template:
                assert surface_sources in setup_template, (
                    "pygame's Setup.Android.SDL2.in template changed - "
                    "update the simd_blitters_sse2.c patch in p4a-recipes/pygame"
                )
                setup_template = setup_template.replace(
                    surface_sources, surface_sources + " " + missing_simd_source
                )
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

[app]
title = Dungeon Crawler
package.name = dungeoncrawler
package.domain = com.germandudexx
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
version = 0.1

# pygame pinned to 2.6.1: p4a's bundled pygame recipe (recipes/pygame in
# kivy/python-for-android) hardcodes version 2.1.0 unless overridden here.
# Both 2.1.0 and 2.5.0's checked-in src_c/_sdl2/sdl2.c contain an unqualified
# `#include "longintrepr.h"` left over from the Cython version that generated
# them; that header was dropped from CPython's public Include/ tree and
# breaks against the python3 recipe's modern target CPython. pygame
# regenerated all _sdl2/*.c with a newer Cython starting at 2.5.2, removing
# every longintrepr.h reference (verified directly against the pygame repo
# for 2.5.2, 2.6.0, 2.6.1 and main). Pinning to 2.6.1 here sets p4a's
# VERSION_pygame env var, which the recipe's `version` property reads and
# substitutes into its {version}-templated download URL.
#
# numpy removed entirely: it was only used by sound.py's tone generator
# (rewritten to pure-Python `array`/`math`), and its Android recipe was a
# repeated source of unrelated build breakage (minapi requirements, NDK
# libc++ compile errors, git-tag version format). Root cause turned out to
# be the same as below: numpy 1.26.4 has no PyPI wheels for Python 3.13/3.14,
# and p4a's python3 recipe was silently building 3.14 (see next paragraph) -
# "from versions: none" was pip correctly reporting that, not a sandbox bug.
# Not needed either way since it's gone from the code now.
#
# cython required: pygame 2.5.2+ ships _sdl2 as a .pyx that p4a's hostpython3
# (its own internally-built Python, separate from the CI runner's system
# Python) must compile via `setup.py build_ext`, which fails with "You need
# cython" if it isn't present in that environment. Listing it here makes p4a
# pip-install it into hostpython3 before building pygame.
#
# python3 + hostpython3 pinned to 3.11.15: p4a's python3 recipe currently
# defaults to CPython 3.14.2 (confirmed in its recipe source), a version
# far too new for this whole toolchain - it's what caused the numpy wheel
# problem above AND breaks Cython 0.29.36 (the p4a cython recipe's own
# default, and the newest one the ecosystem actually supports per open p4a
# issue #2919 "Support Cython 3") with "too few arguments to function call"
# compiling Cython's own Scanners.c against 3.14's changed C API. 3.11 was
# p4a's default for ~2 years and is the last version before Python 3.12
# dropped distutils, which many recipes still lean on. hostpython3 is a
# SEPARATE recipe from python3 with its own independent version - both must
# be pinned together or host/target versions mismatch.
#
# setuptools pinned to 69.5.1: recurring community recommendation alongside
# Cython 0.29.x, since newer setuptools drops the legacy distutils shims
# that build leans on. Not confirmed in p4a source, but cheap to pin.
requirements = python3==3.11.15,hostpython3==3.11.15,setuptools==69.5.1,cython==0.29.36,pygame==2.6.1

orientation = landscape
fullscreen = 1

android.permissions =
android.api = 34
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1

[app]
title = Dungeon Crawler
package.name = dungeoncrawler
package.domain = com.germandudexx
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
version = 0.1

# numpy pinned: newer numpy's unique.cpp fails to compile under the NDK's
# libc++ (missing <unordered_map> include upstream, exposed as a hard error
# there). 1.26.4 predates that file and builds cleanly under p4a.
#
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
requirements = python3,pygame==2.6.1,numpy==v1.26.4

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

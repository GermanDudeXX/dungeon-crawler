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
requirements = python3,pygame,numpy==v1.26.4

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

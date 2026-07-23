[app]
title = Dungeon Crawler
package.name = dungeoncrawler
package.domain = com.germandudexx
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
version = 0.1

requirements = python3,pygame,numpy

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

"""The updater must verify TLS, and must work where the platform has no
CA store of its own (Android).

It downloads an executable that then runs, so this is a security check as
much as a connectivity one: a "fix" that disabled verification would make
the update channel trivially hijackable.
"""
import os
import ssl
import sys
import urllib.request

sys.path.insert(0, r"C:\Users\budzm\dungeon-crawler")
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"

import constants as C
import updater

fails = []

# --- 1. the bundle ships and looks like a real CA store ---
if not os.path.exists(C.CA_BUNDLE_PATH):
    fails.append(f"CA bundle missing at {C.CA_BUNDLE_PATH}")
else:
    data = open(C.CA_BUNDLE_PATH, encoding="utf-8").read()
    n = data.count("BEGIN CERTIFICATE")
    if n < 50:
        fails.append(f"CA bundle only holds {n} certificates - looks truncated")
    else:
        print(f"  CA bundle present: {n} root certificates")

# --- 2. verification must be ON ---
ctx = updater._ssl_context()
if ctx.verify_mode != ssl.CERT_REQUIRED:
    fails.append(f"verification is not required (verify_mode={ctx.verify_mode})")
elif not ctx.check_hostname:
    fails.append("hostname checking is disabled")
else:
    print("  context verifies certificates and hostnames")

loaded = len(ctx.get_ca_certs())
print(f"  context loaded {loaded} CA certificates")
if loaded == 0:
    fails.append("no CA certificates loaded into the context")

# --- 3. it must reject a bad certificate, not wave it through ---
try:
    urllib.request.urlopen("https://expired.badssl.com/", timeout=20,
                           context=updater._ssl_context())
    fails.append("an expired certificate was ACCEPTED - verification is broken")
except urllib.error.URLError as exc:
    if "CERTIFICATE_VERIFY_FAILED" in str(exc) or "certificate" in str(exc).lower():
        print("  correctly rejects an expired certificate")
    else:
        print(f"  (expired-cert probe inconclusive: {exc})")
except Exception as exc:      # noqa: BLE001 - network flakiness is not a failure
    print(f"  (expired-cert probe skipped: {exc})")

# --- 4. and it must accept GitHub, which is what it actually talks to ---
try:
    info = updater.check_for_update()
    print(f"  reached the GitHub API over verified TLS (update: {info and info['build']})")
except Exception as exc:      # noqa: BLE001
    fails.append(f"could not reach GitHub with the bundled roots: {exc}")

# --- 5. the bundle must be packaged for BOTH platforms ---
spec = open(r"C:\Users\budzm\dungeon-crawler\buildozer.spec", encoding="utf-8").read()
inc = next((l for l in spec.splitlines() if l.startswith("source.include_exts")), "")
if "pem" not in inc:
    fails.append("buildozer.spec does not package .pem - Android would ship without the bundle")
else:
    print("  buildozer packages .pem")

pyi = open(r"C:\Users\budzm\dungeon-crawler\DungeonCrawler.spec", encoding="utf-8").read()
if "('assets', 'assets')" not in pyi:
    fails.append("PyInstaller spec does not bundle the assets directory")
else:
    print("  PyInstaller bundles the assets directory")

if fails:
    print("\nFAILURES:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("\nALL TLS CHECKS PASSED")

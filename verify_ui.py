"""
Verify Master UI/UX Design System Implementation
Validates design tokens, typography, surfaces, motion, and accessibility.
"""

import os
import sys

def verify():
    print("=" * 70)
    print("MASTER UI/UX DESIGN SYSTEM VERIFICATION")
    print("=" * 70)
    
    passed = 0
    total = 9
    
    # 1. Check assets/style.css exists
    print("\n[1/9] Checking assets/style.css exists...")
    if os.path.exists("assets/style.css"):
        print("  [PASS] assets/style.css found")
        passed += 1
    else:
        print("  [FAIL] assets/style.css missing")
        return False
    
    with open("assets/style.css", "r", encoding="utf-8") as f:
        css = f.read()

    # 2. Check CSS size
    print("\n[2/9] Checking CSS file size...")
    size = os.path.getsize("assets/style.css")
    print(f"  Size: {size:,} bytes")
    if 13000 <= size <= 28000:
        print(f"  [PASS] Size within expected range (13,000-28,000 bytes)")
        passed += 1
    else:
        print(f"  [FAIL] Size {size} out of range (expected 13,000-28,000 bytes)")
    
    # 3. Check Google Fonts in CSS
    print("\n[3/9] Checking Google Fonts import...")
    if "fonts.googleapis.com" in css and "Inter" in css and "JetBrains+Mono" in css:
        print("  [PASS] Google Fonts (Inter + JetBrains Mono) imported")
        passed += 1
    else:
        print("  [FAIL] Google Fonts import missing required fonts")
    
    # 4. Check Master Design Tokens (§1-§3)
    print("\n[4/9] Checking Master Design Tokens (colors, radius, spacing, z-index)...")
    core_tokens = [
        "--bg-primary:", "--bg-surface:", "--bg-glass-solid:", "--bg-inverse:",
        "--accent-primary:", "--accent-danger:", "--accent-success:", "--accent-warning:",
        "--text-primary:", "--text-secondary:", "--text-inverse:",
        "--border-dim:", "--shadow-glass:",
        "--radius-sm:", "--radius-md:", "--radius-lg:", "--radius-pill:",
        "--space-4:", "--space-8:", "--space-16:", "--space-24:", "--space-32:",
        "--z-sticky-header:", "--font-primary:", "--font-mono:"
    ]
    missing_tokens = [t for t in core_tokens if t not in css]
    if not missing_tokens:
        print("  [PASS] All 25 core Master Design tokens present")
        passed += 1
    else:
        print(f"  [FAIL] Missing tokens: {missing_tokens}")
    
    # 5. Check Unified Legacy Token Compatibility
    print("\n[5/9] Checking unified token compatibility...")
    compat_tokens = ["--bg:", "--surface:", "--accent:", "--text:", "--font-sans:"]
    missing_compat = [t for t in compat_tokens if t not in css]
    if not missing_compat:
        print("  [PASS] All unified token aliases verified")
        passed += 1
    else:
        print(f"  [FAIL] Missing compatibility tokens: {missing_compat}")

    with open("app.py", "r", encoding="utf-8") as f:
        app = f.read()

    # 6. Check app.py loads CSS
    print("\n[6/9] Checking app.py loads CSS...")
    if "style.css" in app and "<style>" in app:
        print("  [PASS] app.py loads style.css")
        passed += 1
    else:
        print("  [FAIL] app.py does not load style.css")
    
    # 7. Check floating nav capsule
    print("\n[7/9] Checking floating navigation capsule...")
    if "nav-capsule" in app and "#panel-a" in app:
        print("  [PASS] Floating nav capsule present with anchor routing")
        passed += 1
    else:
        print("  [FAIL] Floating nav capsule missing")
    
    # 8. Check panel headers have small-caps badges
    print("\n[8/9] Checking panel headers...")
    panels = ["0.1 / Feature A", "0.2 / Feature B", "0.3 / Feature C", "0.4 / Feature D", "0.5 / Feature E"]
    missing_panels = [p for p in panels if p not in app]
    if not missing_panels:
        print("  [PASS] All 5 panel headers have small-caps / eyebrow badges")
        passed += 1
    else:
        print(f"  [FAIL] Missing panel headers: {missing_panels}")
    
    # 9. Check Motion & Accessibility (§10, §11)
    print("\n[9/9] Checking motion curve and reduced-motion support...")
    has_easing = "cubic-bezier(0.2, 1, 0.3, 1)" in css
    has_reduced = "prefers-reduced-motion" in css
    has_keyframes = "@keyframes float" in css and "@keyframes pulse" in css
    if has_easing and has_reduced and has_keyframes:
        print("  [PASS] Universal easing, keyframes, and reduced-motion media query present")
        passed += 1
    else:
        print(f"  [FAIL] Motion/Accessibility incomplete: easing={has_easing}, reduced={has_reduced}, keyframes={has_keyframes}")

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} checks passed")
    print("=" * 70)
    
    if passed == total:
        print("\n[SUCCESS] ALL CHECKS PASSED - MASTER UI/UX DESIGN SYSTEM FULLY APPLIED!")
        return True
    else:
        print(f"\n[WARNING] {total - passed} checks failed - review issues above")
        return False

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)

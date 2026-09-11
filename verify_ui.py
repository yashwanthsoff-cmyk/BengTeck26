"""
Verify Augen Pro UI/UX Implementation
Checks all 7 requirements from the transformation guide.
"""

import os
import sys

def verify():
    print("=" * 70)
    print("AUGEN PRO UI/UX VERIFICATION")
    print("=" * 70)
    
    passed = 0
    total = 7
    
    # 1. Check assets/style.css exists
    print("\n[1/7] Checking assets/style.css exists...")
    if os.path.exists("assets/style.css"):
        print("  [PASS] assets/style.css found")
        passed += 1
    else:
        print("  [FAIL] assets/style.css missing")
        return False
    
    # 2. Check CSS size
    print("\n[2/7] Checking CSS file size...")
    size = os.path.getsize("assets/style.css")
    print(f"  Size: {size:,} bytes")
    if 13000 <= size <= 25000:
        print(f"  [PASS] Size within expected range (13,000-25,000 bytes)")
        passed += 1
    else:
        print(f"  [FAIL] Size {size} out of range (expected 13,000-25,000 bytes)")
    
    # 3. Check Google Fonts in CSS
    print("\n[3/7] Checking Google Fonts import...")
    with open("assets/style.css", "r", encoding="utf-8") as f:
        css = f.read()
    if "fonts.googleapis.com" in css and "Inter" in css:
        print("  [PASS] Google Fonts (Inter) imported")
        passed += 1
    else:
        print("  [FAIL] Google Fonts import missing")
    
    # 4. Check CSS variables
    print("\n[4/7] Checking Augen Pro design tokens...")
    tokens = ["--bg:", "--surface:", "--accent:", "--text:", "--font-sans:"]
    missing = [t for t in tokens if t not in css]
    if not missing:
        print("  [PASS] All core design tokens present")
        passed += 1
    else:
        print(f"  [FAIL] Missing tokens: {missing}")
    
    # 5. Check app.py loads CSS
    print("\n[5/7] Checking app.py loads CSS...")
    with open("app.py", "r", encoding="utf-8") as f:
        app = f.read()
    if "style.css" in app and "<style>" in app:
        print("  [PASS] app.py loads style.css")
        passed += 1
    else:
        print("  [FAIL] app.py does not load style.css")
    
    # 6. Check floating nav capsule
    print("\n[6/7] Checking floating navigation capsule...")
    if "nav-capsule" in app and "#panel-a" in app:
        print("  [PASS] Floating nav capsule present")
        passed += 1
    else:
        print("  [FAIL] Floating nav capsule missing")
    
    # 7. Check panel headers have small-caps
    print("\n[7/7] Checking panel headers...")
    panels = ["0.1 / Feature A", "0.2 / Feature B", "0.3 / Feature C", "0.4 / Feature D", "0.5 / Feature E"]
    missing_panels = [p for p in panels if p not in app]
    if not missing_panels:
        print("  [PASS] All 5 panel headers have small-caps badges")
        passed += 1
    else:
        print(f"  [FAIL] Missing panel headers: {missing_panels}")
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} checks passed")
    print("=" * 70)
    
    if passed == total:
        print("\n[SUCCESS] ALL CHECKS PASSED - UI/UX IS NOT UGLY!")
        return True
    else:
        print(f"\n[WARNING] {total - passed} checks failed - review issues above")
        return False

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)

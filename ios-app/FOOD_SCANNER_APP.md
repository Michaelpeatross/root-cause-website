# Root Cause on your iPhone

I cannot publish to the App Store for you. Apple only accepts builds from **your** Apple Developer account.

## Use it like an app today (no store wait)

1. On the iPhone, open Safari (not the in-app Tesla/Instagram browser).
2. Go to https://www.root-cause-test.com/login and sign in.
3. Tap the **Share** button → **Add to Home Screen**.
4. Name it **Root Cause**.
5. Open the icon. It runs full screen. Stay logged in unless you tap Logout.

That icon opens the food scanner. Camera and plate photo work the same as the site.

## Real App Store app (you submit)

Need:
- A Mac with Xcode
- Apple Developer Program, $99/year: https://developer.apple.com/programs/
- Bundle ID such as `com.rootcause.scanner`

Steps:
1. Xcode → New Project → iOS App → SwiftUI.
2. Drop in `FoodScannerWebApp.swift` as the main screen.
3. Info.plist camera text: `Scan grocery barcodes and meal photos.`
4. Signing & Capabilities → your Team.
5. Test on your iPhone.
6. Product → Archive → Distribute → App Store Connect.
7. Screenshots, privacy policy URL (your site), submit for review.

Review often takes 1–3 days. Login cookies persist in the app so you do not sign in every scan.

## Why the website still asks for login sometimes

Safari can drop the session if you clear data or use a private tab. The home-screen app and the Xcode wrapper keep the same cookie store, so one login lasts until you log out.

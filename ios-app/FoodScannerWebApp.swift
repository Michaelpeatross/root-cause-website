import SwiftUI
import WebKit

/// Minimal App Store wrapper: opens Root Cause and keeps the login cookie.
/// Xcode → New iOS App → replace ContentView with this file.
/// Signing: your Team + bundle id, e.g. com.rootcause.scanner
/// Info.plist: NSCameraUsageDescription = "Scan grocery barcodes and meal photos."

struct FoodScannerWebApp: View {
    var body: some View {
        ScannerWebView(url: URL(string: "https://www.root-cause-test.com/food-scanner")!)
            .ignoresSafeArea()
    }
}

struct ScannerWebView: UIViewRepresentable {
    let url: URL
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        let view = WKWebView(frame: .zero, configuration: config)
        view.uiDelegate = context.coordinator
        view.navigationDelegate = context.coordinator
        view.scrollView.contentInsetAdjustmentBehavior = .never
        view.load(URLRequest(url: url))
        return view
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator() }
    class Coordinator: NSObject, WKUIDelegate, WKNavigationDelegate {
        func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
            decisionHandler(.grant)
        }
    }
}

# Root Cause Health — iOS App (App Store Ready Starter)

This folder contains everything you need to build a real native iOS app and publish it to the Apple App Store.

## Why a native iOS app is much better

- Direct access to Apple Health data using **HealthKit** (no manual "Export All Health Data" zip needed).
- Much better user experience.
- Can run in background / periodic sync (with permissions).
- Feels like a real app on the user's iPhone.
- Can request specific metrics (HRV, sleep stages, resting heart rate, steps, etc.).

## Current Status (Backend Ready)

Your Flask backend already has:
- `/api/client/upload_health` — accepts email + password + file (for the desktop tool).
- Light uploads (won't crash the server with big files).
- Recent-data focus in the summarizer.

For the iOS app we will send structured JSON data instead of a huge XML file.

## Step-by-step: Build & Publish to App Store

### 1. Requirements
- Mac computer with Xcode (free from App Store)
- Apple Developer account ($99/year)
- An iPhone for testing

### 2. Create the Xcode Project
1. Open Xcode → Create New Project → iOS → App (SwiftUI or UIKit).
2. Name it something like **"Root Cause Health"**.
3. Bundle ID: `com.yourcompany.rootcausehealth` (change to your own).

### 3. Add HealthKit Capability
- Go to project settings → Signing & Capabilities → + Capability → HealthKit.
- In Info.plist add:
  ```xml
  <key>NSHealthShareUsageDescription</key>
  <string>We need access to your Apple Health data (heart rate, sleep, activity) to send insights to your Root Cause practitioner.</string>
  ```

### 4. Key Code (Swift)

**HealthDataManager.swift** (core logic)

```swift
import HealthKit

class HealthDataManager {
    let healthStore = HKHealthStore()
    
    func requestAuthorization(completion: @escaping (Bool) -> Void) {
        let typesToRead: Set<HKObjectType> = [
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.quantityType(forIdentifier: .stepCount)!,
            HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN)!,
            HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!,
            HKObjectType.quantityType(forIdentifier: .restingHeartRate)!
        ]
        
        healthStore.requestAuthorization(toShare: [], read: typesToRead) { success, error in
            completion(success)
        }
    }
    
    func fetchRecentData(completion: @escaping ([String: Any]) -> Void) {
        // Query last 30 days of key metrics
        let calendar = Calendar.current
        let endDate = Date()
        let startDate = calendar.date(byAdding: .day, value: -30, to: endDate)!
        
        var results: [String: Any] = [:]
        
        // Example: Heart Rate samples
        let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate)!
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: hrType, predicate: predicate, limit: 500, sortDescriptors: nil) { _, samples, _ in
            if let samples = samples as? [HKQuantitySample] {
                let values = samples.map { $0.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute())) }
                results["heart_rate"] = [
                    "count": values.count,
                    "avg": values.reduce(0, +) / Double(max(values.count, 1)),
                    "min": values.min() ?? 0,
                    "max": values.max() ?? 0
                ]
            }
            completion(results)
        }
        
        healthStore.execute(query)
    }
}
```

**Upload to your backend**

```swift
func uploadToRootCause(email: String, password: String, data: [String: Any], completion: @escaping (Bool, String) -> Void) {
    let url = URL(string: "https://www.root-cause-test.com/api/client/upload_health")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    
    let boundary = "Boundary-\(UUID().uuidString)"
    request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
    
    var body = Data()
    
    // Add credentials + JSON data as a file
    func addField(name: String, value: String) {
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(value)\r\n".data(using: .utf8)!)
    }
    
    addField(name: "email", value: email)
    addField(name: "password", value: password)
    
    // Send health data as a small JSON file
    if let jsonData = try? JSONSerialization.data(withJSONObject: data, options: []) {
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"health_data.json\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/json\r\n\r\n".data(using: .utf8)!)
        body.append(jsonData)
        body.append("\r\n".data(using: .utf8)!)
    }
    
    body.append("--\(boundary)--\r\n".data(using: .utf8)!)
    request.httpBody = body
    
    URLSession.shared.dataTask(with: request) { data, response, error in
        if let data = data,
           let result = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            let success = result["success"] as? Bool ?? false
            let msg = result["message"] as? String ?? "Uploaded"
            completion(success, msg)
        } else {
            completion(false, error?.localizedDescription ?? "Upload failed")
        }
    }.resume()
}
```

### 5. Full Simple App Flow (SwiftUI example)

```swift
struct ContentView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var status = "Tap button to connect Apple Health"
    let manager = HealthDataManager()

    var body: some View {
        VStack(spacing: 20) {
            Text("Root Cause Health")
                .font(.largeTitle)

            TextField("Email", text: $email)
            SecureField("Password", text: $password)

            Button("Connect Apple Health & Send Data") {
                manager.requestAuthorization { granted in
                    if granted {
                        manager.fetchRecentData { data in
                            uploadToRootCause(email: email, password: password, data: data) { success, msg in
                                status = success ? "✅ Sent to Grok!\n\n" + msg : "❌ " + msg
                            }
                        }
                    }
                }
            }
            .buttonStyle(.borderedProminent)

            Text(status)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}
```

### 6. Next Steps to Publish

1. Add proper error handling + nice UI.
2. Store credentials securely (Keychain).
3. Add background delivery for new data (advanced).
4. Build archive in Xcode → Distribute App → App Store Connect.
5. Fill in App Store metadata, screenshots, privacy policy.
6. Submit for review.

## Recommended Architecture

- Use the existing `/api/client/upload_health` (it accepts files).
- Send a small JSON file containing summarized metrics (as shown above).
- On the backend side (future improvement): accept JSON and store it nicely.

## Backend API You Can Use Today

- `POST https://www.root-cause-test.com/api/client/upload_health`
  - Form fields: `email`, `password`, `file` (can be .json or .xml)

## Support

If you want me to:
- Improve the backend to accept clean JSON health data
- Add token-based auth (instead of sending password every time)
- Generate proper app icons
- Write more screens (history, sync status)

...just tell me and I'll add it to the Python project.

This gives you a real path to having a downloadable app on the App Store.

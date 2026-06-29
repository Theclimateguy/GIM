import Foundation
import Security

/// Minimal macOS Keychain wrapper for the cloud-LLM API key.
///
/// The key is a user secret, so it must NOT live in `UserDefaults` (a plaintext
/// plist under ~/Library/Preferences readable by any process running as the
/// user). The Keychain stores it encrypted and scoped to this device. Only the
/// API key goes here; non-secret settings (provider, model, base URL) stay in
/// `UserDefaults`.
enum Keychain {
    static let service = "com.gim17.app.llm"

    /// Store (or, when `value` is empty, remove) the secret for `account`.
    static func set(_ value: String, account: String) {
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(base as CFDictionary)
        guard !value.isEmpty else { return }
        var add = base
        add[kSecValueData as String] = Data(value.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    /// Read the secret for `account`, or "" if absent.
    static func get(account: String) -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let str = String(data: data, encoding: .utf8) else {
            return ""
        }
        return str
    }

    static func delete(account: String) {
        set("", account: account)
    }
}

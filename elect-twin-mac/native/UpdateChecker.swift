import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

// Metadata-only updater. Never downloads, mounts, installs, or executes an asset.
struct UpdateVersion: Comparable {
    let numbers: [Int]
    let prerelease: [String]

    init?(_ raw: String) {
        let pattern = #"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"#
        guard raw.utf8.count <= 128,
              let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: raw, range: NSRange(raw.startIndex..., in: raw)),
              match.range.length == raw.utf16.count else { return nil }
        func group(_ index: Int) -> String? {
            guard let range = Range(match.range(at: index), in: raw) else { return nil }
            return String(raw[range])
        }
        let parsed = (1...3).compactMap { group($0).flatMap(Int.init) }
        guard parsed.count == 3 else { return nil }
        let pre = group(4)?.split(separator: ".").map(String.init) ?? []
        guard !pre.contains(where: { $0.allSatisfy(\.isNumber) && $0.count > 1 && $0.first == "0" }) else { return nil }
        numbers = parsed
        prerelease = pre
    }

    var core: String { numbers.map(String.init).joined(separator: ".") }

    static func < (lhs: Self, rhs: Self) -> Bool {
        if lhs.numbers != rhs.numbers { return lhs.numbers.lexicographicallyPrecedes(rhs.numbers) }
        if lhs.prerelease.isEmpty { return false }
        if rhs.prerelease.isEmpty { return true }
        for (a, b) in zip(lhs.prerelease, rhs.prerelease) where a != b {
            let aNumeric = a.allSatisfy(\.isNumber), bNumeric = b.allSatisfy(\.isNumber)
            if aNumeric && bNumeric { return a.count == b.count ? a < b : a.count < b.count }
            if aNumeric != bNumeric { return aNumeric }
            return a < b
        }
        return lhs.prerelease.count < rhs.prerelease.count
    }
}

enum UpdateChannel: String { case stable, beta }

struct UpdateAsset: Decodable {
    let name: String
    let state: String
    let size: Int64
    let browser_download_url: String
}

struct UpdateRelease: Decodable {
    let tag_name: String
    let draft: Bool
    let prerelease: Bool
    let html_url: String
    let assets: [UpdateAsset]
}

struct AvailableUpdate {
    let tag: String
    let version: UpdateVersion
    let releaseURL: URL
    let downloadURL: URL
}

enum UpdateCheckError: Error, LocalizedError {
    case configuration, invalidResponse, tooLarge, redirected, unavailable(Int), network

    var errorDescription: String? {
        switch self {
        case .configuration: return "This build does not contain a valid release version."
        case .invalidResponse: return "GitHub returned an unreadable release list. Try again later."
        case .tooLarge: return "GitHub's release list exceeded the update check's size limit."
        case .redirected: return "The update source redirected unexpectedly. No download was started."
        case .unavailable(let code):
            if code == 403 || code == 429 { return "GitHub is limiting requests. Try again later." }
            if code == 404 { return "The GitHub release source is currently unavailable. Try again later." }
            return "GitHub is unavailable (HTTP \(code)). Try again later."
        case .network: return "Could not reach GitHub. Check your connection and try again."
        }
    }
}

enum UpdateFeed {
    static let repository = "bagatawaya/elect-twin"
    // /latest excludes the repository's beta releases. Inspect published releases instead.
    static let endpoint = URL(string: "https://api.github.com/repos/\(repository)/releases?per_page=100")!
    static let maxBytes = 1_048_576

    static func trustedURL(_ raw: String, path: String) -> URL? {
        guard let parts = URLComponents(string: raw), parts.scheme == "https",
              parts.host == "github.com", parts.user == nil, parts.password == nil,
              parts.port == nil, parts.query == nil, parts.fragment == nil,
              parts.percentEncodedPath == path else { return nil }
        return parts.url
    }

    static func select(_ data: Data, installed: String, channel: UpdateChannel,
                       architecture: String) throws -> AvailableUpdate? {
        guard let current = UpdateVersion(installed), ["arm64", "x86_64"].contains(architecture) else {
            throw UpdateCheckError.configuration
        }
        guard data.count <= maxBytes else { throw UpdateCheckError.tooLarge }
        guard let releases = try? JSONDecoder().decode([UpdateRelease].self, from: data),
              releases.count <= 100 else { throw UpdateCheckError.invalidResponse }
        var best: AvailableUpdate?
        for release in releases {
            guard !release.draft, let version = UpdateVersion(release.tag_name), version > current,
                  channel == .beta || (!release.prerelease && version.prerelease.isEmpty),
                  let releaseURL = trustedURL(release.html_url,
                      path: "/\(repository)/releases/tag/\(release.tag_name)") else { continue }
            // Explicit filename contract. Ignore source archives, Windows/Intel installers,
            // partially uploaded files, arbitrary URLs, and releases without checksum sidecars.
            let stems = ["OpenTwin", "Elect-Twin"]
            let versions = [version.core, String(release.tag_name.drop(while: { $0 == "v" }))]
            let names = stems.flatMap { stem in versions.flatMap { value in
                [architecture, "universal"].flatMap { arch in
                    ["\(stem)-\(value)-\(arch).dmg", "\(stem)-\(value)-\(arch)-internal.dmg"]
                }
            }}
            guard let asset = release.assets.first(where: { item in
                names.contains(item.name) && item.state == "uploaded" && item.size > 0 && item.size <= 2_147_483_648 &&
                trustedURL(item.browser_download_url,
                    path: "/\(repository)/releases/download/\(release.tag_name)/\(item.name)") != nil &&
                release.assets.contains(where: { checksum in
                    checksum.name == item.name + ".sha256" && checksum.state == "uploaded" &&
                    checksum.size > 0 && checksum.size <= 4096 &&
                    trustedURL(checksum.browser_download_url,
                        path: "/\(repository)/releases/download/\(release.tag_name)/\(checksum.name)") != nil
                })
            }), let downloadURL = URL(string: asset.browser_download_url) else { continue }
            if best == nil || version > best!.version {
                best = AvailableUpdate(tag: release.tag_name, version: version,
                                       releaseURL: releaseURL, downloadURL: downloadURL)
            }
        }
        return best
    }

    static func request() -> URLRequest {
        var request = URLRequest(url: endpoint, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("2022-11-28", forHTTPHeaderField: "X-GitHub-Api-Version")
        request.setValue("OpenTwin-Update-Check", forHTTPHeaderField: "User-Agent")
        // No tokens, account IDs, device IDs, local URLs, project data, or installed version.
        return request
    }
}

// All mutable state is confined to the serial delegate queue. Completion is delivered
// exactly once on the main queue, including cancellation and oversize/redirect failures.
final class UpdateFetch: NSObject, URLSessionDataDelegate, @unchecked Sendable {
    private let protocolClasses: [AnyClass]?
    private var session: URLSession?
    private var bytes = Data()
    private var failure: UpdateCheckError?
    private var completion: ((Result<Data, UpdateCheckError>) -> Void)?

    init(protocolClasses: [AnyClass]? = nil) {
        self.protocolClasses = protocolClasses
        super.init()
    }

    func start(_ completion: @escaping (Result<Data, UpdateCheckError>) -> Void) {
        precondition(session == nil)
        self.completion = completion
        let config = URLSessionConfiguration.ephemeral
        if let protocolClasses { config.protocolClasses = protocolClasses }
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.urlCredentialStorage = nil
        config.urlCache = nil
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 20
        let queue = OperationQueue()
        queue.maxConcurrentOperationCount = 1
        session = URLSession(configuration: config, delegate: self, delegateQueue: queue)
        session?.dataTask(with: UpdateFeed.request()).resume()
    }

    func cancel() { session?.invalidateAndCancel() }

    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        failure = .redirected
        completionHandler(nil)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let http = response as? HTTPURLResponse else {
            failure = .invalidResponse; completionHandler(.cancel); return
        }
        guard http.statusCode == 200 else {
            if failure == nil { failure = .unavailable(http.statusCode) }
            completionHandler(.cancel); return
        }
        guard response.expectedContentLength <= Int64(UpdateFeed.maxBytes) else {
            failure = .tooLarge; completionHandler(.cancel); return
        }
        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard failure == nil else { return }
        guard bytes.count + data.count <= UpdateFeed.maxBytes else {
            failure = .tooLarge; dataTask.cancel(); return
        }
        bytes.append(data)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        let result: Result<Data, UpdateCheckError>
        if let failure { result = .failure(failure) }
        else if error != nil { result = .failure(.network) }
        else { result = .success(bytes) }
        let callback = completion
        completion = nil
        session.finishTasksAndInvalidate()
        DispatchQueue.main.async { callback?(result) }
    }
}

// Persisted attempt time, rather than success time, prevents failure/relaunch loops.
struct UpdateSchedule {
    static let interval: TimeInterval = 24 * 60 * 60
    static func isDue(lastAttempt: Date?, now: Date) -> Bool {
        guard let lastAttempt else { return true }
        let age = now.timeIntervalSince(lastAttempt)
        return age < 0 || age >= interval
    }
}

// "Later" reminds at most daily; "Skip This Version" suppresses that tag only.
enum UpdateNotificationPolicy {
    static func shouldNotify(tag: String, skippedTag: String?, lastTag: String?,
                             lastDate: Date?, now: Date) -> Bool {
        guard skippedTag != tag else { return false }
        return lastTag != tag || UpdateSchedule.isDue(lastAttempt: lastDate, now: now)
    }
}

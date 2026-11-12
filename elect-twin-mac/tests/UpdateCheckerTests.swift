import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

private final class StubProtocol: URLProtocol, @unchecked Sendable {
    static var respond: ((StubProtocol) -> Void)?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() { Self.respond?(self) }
    override func stopLoading() {}
    func reply(status: Int = 200, data: Data = Data("[]".utf8), length: Int? = nil) {
        let headers = length.map { ["Content-Length": String($0)] } ?? [:]
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }
}

@main
struct UpdateCheckerTests {
    static var assertions = 0
    static func expect(_ condition: @autoclosure () throws -> Bool, _ label: String) {
        let passed: Bool
        do { passed = try condition() } catch { fatalError("FAIL: \(label): \(error)") }
        guard passed else { fatalError("FAIL: \(label)") }
        assertions += 1
    }
    static func rejects(_ label: String, _ body: () throws -> Void) {
        do { try body(); fatalError("FAIL: \(label)") } catch { assertions += 1 }
    }
    static func release(_ tag: String, prerelease: Bool = false, draft: Bool = false,
                        arch: String = "arm64", checksum: Bool = true) -> [String: Any] {
        let core = UpdateVersion(tag)?.core ?? "0.0.0"
        let name = "Elect-Twin-\(core)-\(arch)-internal.dmg"
        let prefix = "https://github.com/\(UpdateFeed.repository)/releases/"
        var assets: [[String: Any]] = [["name": name, "state": "uploaded", "size": 19_000_000,
            "browser_download_url": prefix + "download/\(tag)/\(name)"]]
        if checksum { assets.append(["name": name + ".sha256", "state": "uploaded", "size": 102,
            "browser_download_url": prefix + "download/\(tag)/\(name).sha256"]) }
        return ["tag_name": tag, "draft": draft, "prerelease": prerelease,
                "html_url": prefix + "tag/\(tag)", "assets": assets]
    }
    static func select(_ releases: [[String: Any]], installed: String = "0.4.0-beta",
                       channel: UpdateChannel = .beta, architecture: String = "arm64") throws -> AvailableUpdate? {
        try UpdateFeed.select(JSONSerialization.data(withJSONObject: releases),
                              installed: installed, channel: channel, architecture: architecture)
    }
    private static func fetch(_ respond: @escaping (StubProtocol) -> Void, cancel: Bool = false) -> Result<Data, UpdateCheckError> {
        StubProtocol.respond = respond
        let request = UpdateFetch(protocolClasses: [StubProtocol.self])
        var result: Result<Data, UpdateCheckError>?
        var callbacks = 0
        request.start { value in callbacks += 1; result = value }
        if cancel { request.cancel() }
        let deadline = Date().addingTimeInterval(3)
        while result == nil && Date() < deadline { RunLoop.main.run(until: Date().addingTimeInterval(0.01)) }
        expect(result != nil, "network callback completes")
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))
        expect(callbacks == 1, "network callback is delivered once")
        return result!
    }
    static func failure(_ result: Result<Data, UpdateCheckError>, contains: String) {
        if case .failure(let error) = result { expect(error.localizedDescription.contains(contains), "network error: \(contains)") }
        else { fatalError("Expected network failure: \(contains)") }
    }
    static func main() throws {
        let ordered = ["0.4.0-alpha", "0.4.0-alpha.1", "0.4.0-alpha.beta", "0.4.0-beta",
            "0.4.0-beta.2", "0.4.0-beta.11", "0.4.0-rc.1", "0.4.0", "0.4.1", "0.10.0", "1.0.0"]
        for pair in zip(ordered, ordered.dropFirst()) {
            expect(UpdateVersion(pair.0)! < UpdateVersion(pair.1)!, "semantic ordering \(pair.0) < \(pair.1)")
        }
        expect(UpdateVersion("v1.2.3+build.9") == UpdateVersion("1.2.3+different"), "build metadata does not change precedence")
        expect(UpdateVersion("0.4.0-beta.999999999999999999999")! > UpdateVersion("0.4.0-beta.99999999999999999999")!, "numeric prerelease overflow is safe")
        for invalid in ["", "1", "1.2", "01.2.3", "1.02.3", "1.2.03", "v1.2.3-beta.01", "1.2.3\n", "release/v1.2.3", "1.2.3-", "1.2.3+", "1.2.3;open", "999999999999999999999.0.0"] {
            expect(UpdateVersion(invalid) == nil, "invalid version rejected: \(invalid)")
        }
        expect(try select([]) == nil, "empty release list")
        expect(try select([release("v0.3.0-beta"), release("v0.4.0-beta")]) == nil, "current and older versions not offered")
        expect(try select([release("v0.4.0")])?.tag == "v0.4.0", "stable upgrade from beta")
        expect(try select([release("v0.5.0-beta", prerelease: true)])?.tag == "v0.5.0-beta", "beta channel includes prerelease")
        expect(try select([release("v0.5.0-beta", prerelease: true)], channel: .stable) == nil, "stable excludes flagged prerelease")
        expect(try select([release("v0.5.0-beta")], channel: .stable) == nil, "stable excludes mislabeled prerelease")
        expect(try select([release("v0.5.0", draft: true)]) == nil, "draft ignored")
        expect(try select([release("v0.5.0"), release("v0.10.0"), release("v0.6.0")])?.tag == "v0.10.0", "highest semantic release, not API order")
        expect(try select([release("v0.5.0", arch: "x64")]) == nil, "wrong architecture ignored")
        expect(try select([release("v0.5.0", arch: "universal")]) != nil, "universal installer accepted")
        expect(try select([release("v0.5.0", checksum: false)]) == nil, "missing checksum sidecar ignored")
        expect(try select([release("v0.5.0")], installed: "0.6.0") == nil, "no downgrades")
        var modified = release("v0.5.0")
        modified["html_url"] = "https://evil.example/"
        expect(try select([modified]) == nil, "malicious release URL rejected")
        let expectedPath = "/bagatawaya/elect-twin/releases/tag/v0.5.0"
        for url in ["http://github.com" + expectedPath, "https://github.com.evil.test" + expectedPath,
            "https://github.com:443" + expectedPath, "https://user@github.com" + expectedPath,
            "https://github.com" + expectedPath + "?token=x", "https://github.com" + expectedPath + "#x",
            "https://github.com/bagatawaya/other/releases/tag/v0.5.0", "https://github.com/bagatawaya/elect-twin/releases/tag/%760.5.0"] {
            expect(UpdateFeed.trustedURL(url, path: expectedPath) == nil, "untrusted URL rejected")
        }
        for (key, value) in [("state", "new"), ("browser_download_url", "https://evil.example/installer.dmg"), ("name", "../installer.dmg")] {
            modified = release("v0.5.0")
            var assets = modified["assets"] as! [[String: Any]]
            assets[0][key] = value; modified["assets"] = assets
            expect(try select([modified]) == nil, "bad asset \(key) ignored")
        }
        rejects("malformed JSON rejected") { _ = try UpdateFeed.select(Data("{}".utf8), installed: "0.4.0", channel: .beta, architecture: "arm64") }
        rejects("oversize payload rejected") { _ = try UpdateFeed.select(Data(repeating: 32, count: UpdateFeed.maxBytes + 1), installed: "0.4.0", channel: .beta, architecture: "arm64") }
        rejects("invalid installed version rejected") { _ = try select([], installed: "unknown") }
        rejects("unknown architecture rejected") { _ = try select([], architecture: "riscv") }
        rejects("more than bounded release count rejected") { _ = try select(Array(repeating: release("v0.5.0"), count: 101)) }
        let now = Date(timeIntervalSince1970: 100000)
        expect(UpdateSchedule.isDue(lastAttempt: nil, now: now), "first launch checks")
        expect(!UpdateSchedule.isDue(lastAttempt: now, now: now), "relaunch does not spam")
        expect(!UpdateSchedule.isDue(lastAttempt: now.addingTimeInterval(-86399), now: now), "24 hour throttle")
        expect(UpdateSchedule.isDue(lastAttempt: now.addingTimeInterval(-86400), now: now), "next daily check")
        expect(UpdateSchedule.isDue(lastAttempt: now.addingTimeInterval(3600), now: now), "clock rollback recovers")
        expect(UpdateNotificationPolicy.shouldNotify(tag: "v0.5.0", skippedTag: nil, lastTag: nil, lastDate: nil, now: now), "new update notifies")
        expect(!UpdateNotificationPolicy.shouldNotify(tag: "v0.5.0", skippedTag: "v0.5.0", lastTag: nil, lastDate: nil, now: now), "skipped version suppressed")
        expect(UpdateNotificationPolicy.shouldNotify(tag: "v0.6.0", skippedTag: "v0.5.0", lastTag: "v0.5.0", lastDate: now, now: now), "newer version not suppressed by old skip")
        expect(!UpdateNotificationPolicy.shouldNotify(tag: "v0.5.0", skippedTag: nil, lastTag: "v0.5.0", lastDate: now, now: now), "same-day Later suppressed")
        expect(UpdateNotificationPolicy.shouldNotify(tag: "v0.5.0", skippedTag: nil, lastTag: "v0.5.0", lastDate: now.addingTimeInterval(-86400), now: now), "Later reminds next day")
        let request = UpdateFeed.request()
        expect(request.url == UpdateFeed.endpoint && request.httpMethod == "GET", "fixed read-only release endpoint")
        expect(request.httpBody == nil && request.value(forHTTPHeaderField: "Authorization") == nil, "no personal payload or credentials")
        expect(request.value(forHTTPHeaderField: "User-Agent") == "OpenTwin-Update-Check", "generic user agent")
        expect(request.timeoutInterval == 15, "bounded request deadline")
        let success = fetch { $0.reply() }
        if case .success(let data) = success { expect(data == Data("[]".utf8), "HTTP success") } else { fatalError("Expected success") }
        failure(fetch { $0.reply(status: 403) }, contains: "limiting")
        failure(fetch { $0.reply(status: 429) }, contains: "limiting")
        failure(fetch { $0.reply(status: 404) }, contains: "unavailable")
        failure(fetch { $0.reply(status: 503) }, contains: "HTTP 503")
        failure(fetch { $0.reply(length: UpdateFeed.maxBytes + 1) }, contains: "size limit")
        failure(fetch { $0.reply(data: Data(repeating: 32, count: UpdateFeed.maxBytes + 1)) }, contains: "size limit")
        failure(fetch { $0.client?.urlProtocol($0, didFailWithError: URLError(.notConnectedToInternet)) }, contains: "connection")
        failure(fetch({ _ in }, cancel: true), contains: "connection")
        print("PASS: \(assertions) update-checker assertions; no external network or provider requests.")
    }
}

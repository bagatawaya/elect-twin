import AppKit
import Foundation
import WebKit

private struct RoomsReady: Decodable {
    let ready: Bool
    let urls: [String: String]
}

private struct TwinReady: Decodable {
    let ready: Bool
    let url: String
    let origin: String
}

private enum LaunchError: Error, LocalizedError {
    case missingResource(String)
    case invalidReadyMessage(String)
    case startupTimeout(String)
    case invalidLocalURL(String)

    var errorDescription: String? {
        switch self {
        case .missingResource(let name): return "The bundled \(name) runtime is missing. Reinstall Elect Twin from the original DMG."
        case .invalidReadyMessage(let name): return "The local \(name) engine did not return a valid startup response."
        case .startupTimeout(let name): return "The local \(name) engine did not start within 20 seconds."
        case .invalidLocalURL(let name): return "The \(name) engine returned an unsafe or unreadable local address."
        }
    }
}

private final class ReadyReader {
    var data = Data()
    let ready = DispatchSemaphore(value: 0)
}

@main
final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    static func main() {
        let application = NSApplication.shared
        let delegate = AppDelegate()
        application.delegate = delegate
        application.setActivationPolicy(.regular)
        withExtendedLifetime(delegate) { application.run() }
    }

    var window: NSWindow!
    var webView: WKWebView!
    private var twinProcess: Process?
    private var roomsProcess: Process?
    private var homeURL: URL?
    private var allowedPorts = Set<Int>()
    private var didStart = false
    private var selfTest: NativeSelfTest?
    private lazy var updates = UpdateController(disabledForTest: NativeSelfTest.isRequested)

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSLog("ElectTwin applicationDidFinishLaunching")
        configureWindow()
        configureMenu()
        if NativeSelfTest.isRequested, let runner = NativeSelfTest(app: self) {
            selfTest = runner
            runner.start()
        }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            NSLog("ElectTwin startEngines dispatched")
            self?.startEngines()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        updates.stop()
        stopEngines()
    }

    private func configureWindow() {
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.preferences.tabFocusesLinks = true
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.setValue(false, forKey: "drawsBackground")

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Elect Twin"
        window.subtitle = "Internal test build · local workspace"
        window.minSize = NSSize(width: 920, height: 640)
        window.contentView = webView
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func configureMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About Elect Twin", action: #selector(showAbout), keyEquivalent: "")
        appMenu.addItem(.separator())
        updates.addMenuItems(to: appMenu)
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Elect Twin", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let navigateItem = NSMenuItem()
        main.addItem(navigateItem)
        let navigate = NSMenu(title: "Navigate")
        navigate.addItem(withTitle: "Home", action: #selector(goHome), keyEquivalent: "h").keyEquivalentModifierMask = [.command, .shift]
        navigate.addItem(withTitle: "Back", action: #selector(goBack), keyEquivalent: "[")
        navigate.addItem(withTitle: "Forward", action: #selector(goForward), keyEquivalent: "]")
        navigate.addItem(withTitle: "Reload", action: #selector(reload), keyEquivalent: "r")
        navigateItem.submenu = navigate
        NSApp.mainMenu = main
    }

    private func dataRoot() throws -> URL {
        let args = CommandLine.arguments
        if let index = args.firstIndex(of: "--data-root"), args.indices.contains(index + 1) {
            return URL(fileURLWithPath: args[index + 1], isDirectory: true)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library", isDirectory: true)
            .appendingPathComponent("Application Support", isDirectory: true)
            .appendingPathComponent("Elect Twin", isDirectory: true)
    }

    private func bundledURL(_ path: String) throws -> URL {
        guard let root = Bundle.main.resourceURL else { throw LaunchError.missingResource(path) }
        let url = root.appendingPathComponent(path)
        guard FileManager.default.isExecutableFile(atPath: url.path) else { throw LaunchError.missingResource(path) }
        return url
    }

    private func startEngines() {
        guard !didStart else { return }
        didStart = true
        do {
            let root = try dataRoot()
            try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let roomsHome = root.appendingPathComponent("rooms-home", isDirectory: true)
            let twinData = root.appendingPathComponent("projects.sqlite3").path
            let zooData = root.appendingPathComponent("zoo.sqlite3").path

            let rooms = Process()
            rooms.executableURL = try bundledURL("Rooms/rooms-server")
            var roomsEnvironment = ProcessInfo.processInfo.environment
            roomsEnvironment["HOME"] = roomsHome.path
            let providerEnvironmentKeys = [
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
                "MISTRAL_API_KEY", "GROQ_API_KEY"
            ]
            providerEnvironmentKeys.forEach { roomsEnvironment.removeValue(forKey: $0) }
            rooms.environment = roomsEnvironment
            let roomsOutput = Pipe()
            rooms.standardOutput = roomsOutput
            rooms.standardError = FileHandle.nullDevice
            try rooms.run()
            roomsProcess = rooms
            let roomsReady: RoomsReady = try readReady(rooms, pipe: roomsOutput, name: "Rooms")
            NSLog("ElectTwin roomsReady received: \(roomsReady.ready)")
            guard roomsReady.ready, let jay = roomsReady.urls["jay"], let alex = roomsReady.urls["alex"] else {
                throw LaunchError.invalidReadyMessage("Rooms")
            }
            try recordLocalPorts([jay, alex], name: "Rooms")

            let twin = Process()
            twin.executableURL = try bundledURL("Runtime/twin-server")
            twin.arguments = ["--native", "--port", "0", "--data", twinData,
                              "--zoo-data", zooData]
            var environment = ProcessInfo.processInfo.environment
            environment["ELECT_TWIN_ROOMS_JAY"] = jay
            environment["ELECT_TWIN_ROOMS_ALEX"] = alex
            twin.environment = environment
            let twinOutput = Pipe()
            twin.standardOutput = twinOutput
            twin.standardError = FileHandle.nullDevice
            try twin.run()
            twinProcess = twin
            let twinReady: TwinReady = try readReady(twin, pipe: twinOutput, name: "Twin")
            NSLog("ElectTwin twinReady received: \(twinReady.ready), url: \(twinReady.url)")
            guard twinReady.ready else { throw LaunchError.invalidReadyMessage("Twin") }
            try recordLocalPorts([twinReady.url, twinReady.origin], name: "Twin")
            guard let url = URL(string: twinReady.url), isLoopback(url) else { throw LaunchError.invalidLocalURL("Twin") }

            DispatchQueue.main.async { [weak self] in
                NSLog("ElectTwin loading url: \(url)")
                self?.homeURL = url
                self?.webView.load(URLRequest(url: url))
                if let self { self.updates.start(window: self.window) }
            }
        } catch {
            stopEngines()
            DispatchQueue.main.async { [weak self] in self?.showLaunchError(error) }
        }
    }

    private func readReady<T: Decodable>(_ process: Process, pipe: Pipe, name: String) throws -> T {
        let reader = ReadyReader()
        let handle = pipe.fileHandleForReading
        handle.readabilityHandler = { file in
            let chunk = file.availableData
            if chunk.isEmpty {
                reader.ready.signal()
                return
            }
            reader.data.append(chunk)
            if reader.data.contains(0x0a) { reader.ready.signal() }
        }
        defer { handle.readabilityHandler = nil }
        guard reader.ready.wait(timeout: .now() + 20) == .success else { throw LaunchError.startupTimeout(name) }
        guard process.isRunning || !reader.data.isEmpty,
              let line = reader.data.split(separator: 0x0a).first,
              let value = try? JSONDecoder().decode(T.self, from: Data(line)) else {
            throw LaunchError.invalidReadyMessage(name)
        }
        return value
    }

    private func isLoopback(_ url: URL) -> Bool {
        url.scheme == "http" && url.host == "127.0.0.1" && url.port != nil
    }

    private func recordLocalPorts(_ values: [String], name: String) throws {
        for value in values {
            guard let url = URL(string: value), isLoopback(url), let port = url.port else { throw LaunchError.invalidLocalURL(name) }
            allowedPorts.insert(port)
        }
    }

    private func stopEngines() {
        for process in [twinProcess, roomsProcess] {
            guard let process, process.isRunning else { continue }
            process.terminate()
        }
        twinProcess = nil
        roomsProcess = nil
    }

    private func showLaunchError(_ error: Error) {
        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = "Elect Twin could not start"
        alert.informativeText = error.localizedDescription + "\n\nNo existing prototype data was changed. You can quit and try the copied app again."
        alert.addButton(withTitle: "Quit")
        alert.runModal()
        NSApp.terminate(nil)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "elect-twin" {
            decisionHandler(.cancel)
            if url.host == "home" { goHome() }
            if url.host == "zoo" { goZoo() }
            return
        }
        if isLoopback(url), let port = url.port, allowedPorts.contains(port) {
            decisionHandler(.allow)
            return
        }
        decisionHandler(.cancel)
        if navigationAction.navigationType == .linkActivated, ["http", "https"].contains(url.scheme) {
            NSWorkspace.shared.open(url)
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        window.subtitle = "Local page could not load · use Reload to try again"
    }

    @objc private func goHome() {
        guard let homeURL else { return }
        webView.load(URLRequest(url: homeURL))
    }
    @objc private func goZoo() {
        guard let homeURL,
              var components = URLComponents(url: homeURL, resolvingAgainstBaseURL: false)
        else { goHome(); return }
        components.path = "/zoo"
        guard let zooURL = components.url, isLoopback(zooURL) else { goHome(); return }
        webView.load(URLRequest(url: zooURL))
    }
    @objc private func goBack() { if webView.canGoBack { webView.goBack() } }
    @objc private func goForward() { if webView.canGoForward { webView.goForward() } }
    @objc private func reload() { webView.reload() }

    @objc private func showAbout() {
        let alert = NSAlert()
        alert.messageText = "Elect Twin 0.4.0"
        alert.informativeText = "Apple Silicon internal test build (build 2026111104). Ad-hoc signed; not Developer ID signed or notarized.\n\nProjects, Zoo, and Rooms run locally with separate data stores. No remote accounts, cloud sync, invitations, federation, or live model verification are included."
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

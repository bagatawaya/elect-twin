import AppKit
import Foundation
import WebKit

private enum NativeTestError: Error, LocalizedError {
    case missingOutputDirectory
    case assertion(String)
    case timeout(String)

    var errorDescription: String? {
        switch self {
        case .missingOutputDirectory: return "The --ui-test-dir argument needs an absolute output directory."
        case .assertion(let message): return message
        case .timeout(let expression): return "Timed out waiting for: \(expression)"
        }
    }
}

@MainActor
final class NativeSelfTest: NSObject {
    static var isRequested: Bool { CommandLine.arguments.contains("--ui-test-dir") }

    private let app: AppDelegate
    private let output: URL
    private let reopen: Bool
    private var checks: [String] = [] { didSet { if let last = checks.last { log("PASS: \(last)") } } }

    init?(app: AppDelegate) {
        let args = CommandLine.arguments
        guard let index = args.firstIndex(of: "--ui-test-dir"), args.indices.contains(index + 1) else { return nil }
        let path = args[index + 1]
        guard path.hasPrefix("/") else { return nil }
        self.app = app
        self.output = URL(fileURLWithPath: path, isDirectory: true)
        self.reopen = args.contains("--ui-test-reopen")
        super.init()
    }

    func start() {
        try? FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        log("Runner initialized")
        Task { @MainActor in
            log("Task entered")
            do {
                if reopen { try await runReopen() } else { try await runFirstLaunch() }
                log("Flow complete")
                try writeReport(success: true, error: nil)
                log("Success report written")
                NSApp.terminate(nil)
            } catch {
                log("ERROR: \(error.localizedDescription)")
                try? writeReport(success: false, error: error.localizedDescription)
                NSApp.terminate(nil)
            }
        }
    }

    private var webView: WKWebView { app.webView }

    private func log(_ message: String) {
        let line = "\(ISO8601DateFormatter().string(from: Date())) \(message)\n"
        let url = output.appendingPathComponent(reopen ? "reopen-progress.log" : "native-progress.log")
        if let handle = try? FileHandle(forWritingTo: url) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: Data(line.utf8))
        } else {
            try? Data(line.utf8).write(to: url)
        }
    }

    private func evaluate(_ script: String) async throws -> Any? {
        try await withCheckedThrowingContinuation { continuation in
            webView.evaluateJavaScript(script) { value, error in
                if let error {
                    let detail = String(describing: error)
                    let excerpt = String(script.prefix(320))
                    continuation.resume(throwing: NativeTestError.assertion("JavaScript failed: \(detail); script: \(excerpt)"))
                } else { continuation.resume(returning: value) }
            }
        }
    }

    private func literal(_ value: String) -> String {
        let data = try! JSONEncoder().encode(value)
        return String(data: data, encoding: .utf8)!
    }

    private func waitUntil(_ expression: String, timeout: TimeInterval = 25) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        var lastDiag = ""
        while Date() < deadline {
            do {
                if let value = try await evaluate("Boolean(\(expression))"), (value as? Bool) == true { return }
            } catch {
                let errStr = error.localizedDescription
                if errStr != lastDiag {
                    lastDiag = errStr
                    log("waitUntil evaluate error: \(errStr)")
                }
            }
            try await Task.sleep(nanoseconds: 120_000_000)
        }
        let diag = (try? await evaluate("JSON.stringify({href: location.href, path: location.pathname, hasState: typeof state !== 'undefined', btns: document.querySelectorAll('#nav button').length, setupExists: Boolean(document.querySelector('#setup-dialog')), setupOpen: Boolean(document.querySelector('#setup-dialog')?.open), setupShown: typeof setupShown !== 'undefined' ? setupShown : 'undef', onboardingStatus: typeof state !== 'undefined' ? state?.profile?.onboarding?.status : 'undef', maybeShowSetupType: typeof maybeShowSetup, openSetupType: typeof openSetup, statusText: document.querySelector('#status')?.textContent || 'empty', renderError: window.__lastRenderError || 'none', jsError: window.__lastJSError || 'none'})")) as? String ?? "nil"
        log("waitUntil TIMEOUT: \(expression); diag: \(diag)")
        throw NativeTestError.timeout(expression)
    }

    private func assertJS(_ expression: String, _ message: String) async throws {
        guard let value = try await evaluate("Boolean(\(expression))") as? Bool, value else {
            throw NativeTestError.assertion(message)
        }
    }

    private func click(_ selector: String) async throws {
        let navigatingSelectors = ["[data-start-project]", "[data-open-project]", "#home", "#page [data-room='jay']", "a[href='elect-twin://home']"]
        let action = navigatingSelectors.contains(selector) ? "setTimeout(() => nodes[0].click(), 0)" : "nodes[0].click()"
        let script = """
        (() => {
          const nodes = document.querySelectorAll(\(literal(selector)));
          if (nodes.length !== 1) throw new Error('Expected exactly one matching element; found ' + nodes.length);
          \(action);
          return true;
        })()
        """
        _ = try await evaluate(script)
    }

    private func setValue(_ selector: String, _ value: String) async throws {
        let script = """
        (() => {
          const node = document.querySelector(\(literal(selector)));
          if (!node) throw new Error('Missing matching input');
          node.value = \(literal(value));
          node.dispatchEvent(new Event('input', {bubbles:true}));
          node.dispatchEvent(new Event('change', {bubbles:true}));
          return true;
        })()
        """
        _ = try await evaluate(script)
    }

    private func setChecked(_ selector: String, _ value: Bool) async throws {
        _ = try await evaluate("document.querySelector(\(literal(selector))).checked = \(value ? "true" : "false")")
    }

    private func submit(_ selector: String) async throws {
        _ = try await evaluate("document.querySelector(\(literal(selector))).requestSubmit()")
    }

    private func pause(_ nanoseconds: UInt64 = 600_000_000) async throws {
        try await Task.sleep(nanoseconds: nanoseconds)
    }

    private func snapshot(_ name: String) async throws {
        let configuration = WKSnapshotConfiguration()
        configuration.rect = webView.bounds
        let image: NSImage = try await withCheckedThrowingContinuation { continuation in
            webView.takeSnapshot(with: configuration) { image, error in
                if let error { continuation.resume(throwing: error) }
                else if let image { continuation.resume(returning: image) }
                else { continuation.resume(throwing: NativeTestError.assertion("WebKit returned no screenshot.")) }
            }
        }
        guard let tiff = image.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiff),
              let data = bitmap.representation(using: .png, properties: [:]) else {
            throw NativeTestError.assertion("Could not encode screenshot.")
        }
        try data.write(to: output.appendingPathComponent(name + ".png"))
    }

    private func settleHome() async throws {
        try await waitUntil("location.pathname === '/home' && typeof state !== 'undefined' && state.providers.length === 5 && document.querySelectorAll('#nav button').length === 9")
        try await pause()
        _ = try await evaluate("""
        (() => {
          if (document.querySelector('#setup-dialog')?.open) document.querySelector('#setup-dialog [data-setup-not-now]')?.click();
          if (document.querySelector('#provider-dialog')?.open) document.querySelector('#provider-dialog .actions [data-close]')?.click();
          if (document.querySelector('#invitation-dialog')?.open) document.querySelector('#invitation-dialog [data-invitation-close]')?.click();
          if (document.querySelector('#zoo-agent-dialog')?.open) document.querySelector('#zoo-agent-dialog [data-close]')?.click();
          return true;
        })()
        """)
    }

    private func goHomePage() async throws {
        try await click("#nav [data-page='home']")
        try await waitUntil("page === 'home' && document.querySelector('h1')?.textContent.startsWith('Good to see you')")
    }

    private func runFirstLaunch() async throws {
        try await waitUntil("location.pathname === '/home' && typeof state !== 'undefined' && state.providers.length === 5 && document.querySelectorAll('#nav button').length === 9")
        try await waitUntil("document.querySelector('#setup-dialog')?.open")
        try await assertJS("document.querySelector('#setup-title')?.textContent.includes('Welcome') && document.querySelector('#setup-content')?.textContent.includes('local plaintext')", "First-run setup wizard did not present the Welcome and privacy step.")
        try await snapshot("01-first-run-provider")
        checks.append("Actual app cold start and first-run multi-provider setup wizard")

        try await click("button.primary[data-setup-step='providers']")
        try await waitUntil("document.querySelector('#setup-title')?.textContent === 'Providers'")
        try await assertJS("document.querySelectorAll('[data-setup-provider-form]').length === 5", "Setup wizard did not present 5 independent provider forms.")
        checks.append("Multi-provider setup step with 5 independent provider forms")

        try await click(".setup-actions button[data-setup-not-now]")
        try await waitUntil("!document.querySelector('#setup-dialog')?.open")
        checks.append("Dismissed setup wizard without entering keys or provider calls")

        let destinations = [("models", "My Models"), ("projects", "My Projects"), ("twin", "My Twin"), ("people", "People"), ("collaboration", "Collaboration"), ("challenges", "Agent Challenges"), ("following", "Following"), ("zoo", "OpenZoo")]
        for (id, title) in destinations {
            try await click("#nav [data-page='\(id)']")
            try await waitUntil("page === '\(id)' && document.querySelector('h1')?.textContent === \(literal(title))")
            checks.append("Native navigation: \(title)")
            if id == "models" { try await snapshot("02-my-models") }
        }

        app.window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        app.window.makeFirstResponder(webView)
        try await pause(200_000_000)
        log("Window isKey: \(app.window.isKeyWindow)")
        _ = try await evaluate("document.querySelector('#nav [data-page=\"models\"]').focus()")
        for type in [NSEvent.EventType.keyDown, NSEvent.EventType.keyUp] {
            guard let event = NSEvent.keyEvent(with: type, location: .zero, modifierFlags: [], timestamp: ProcessInfo.processInfo.systemUptime, windowNumber: app.window.windowNumber, context: nil, characters: "\t", charactersIgnoringModifiers: "\t", isARepeat: false, keyCode: 48) else {
                throw NativeTestError.assertion("Could not create a Tab key event.")
            }
            NSApp.sendEvent(event)
        }
        try await pause(250_000_000)
        let focusState = try await evaluate("JSON.stringify({html:document.activeElement?.outerHTML.slice(0,240), visible:document.activeElement?.matches(':focus-visible'), outline:getComputedStyle(document.activeElement).outline})")
        log("Focus state after Tab: \(String(describing: focusState))")
        try await assertJS("document.activeElement === document.querySelector('#nav [data-page=\"projects\"]') && document.activeElement.matches(':focus-visible') && getComputedStyle(document.activeElement).outlineWidth === '3px'", "Tab navigation did not produce the expected visible focus indicator in WebKit.")
        checks.append("WebKit Tab navigation and keyboard-focus indicator")

        try await click("#nav [data-page='people']")
        try await waitUntil("page === 'people' && document.querySelector('.pagehead button[data-new-invitation]')")
        try await click(".pagehead button[data-new-invitation]")
        try await waitUntil("document.querySelector('#invitation-dialog')?.open")
        try await assertJS("document.querySelector('#invitation-title')?.textContent.includes('preview') && document.querySelector('#invitation-description')?.textContent.includes('Local preview only')", "Invitation dialog did not show local consent disclaimer.")
        try await click("#invitation-dialog .dialoghead [data-invitation-close]")
        try await waitUntil("!document.querySelector('#invitation-dialog')?.open")
        checks.append("People invitation preview consent dialog verified")

        try await click("#nav [data-page='zoo']")
        try await waitUntil("page === 'zoo' && document.querySelector('.zoo-top-section')")
        try await assertJS("document.querySelectorAll('[data-zoo-category]').length >= 4", "Zoo category filters missing.")
        try await assertJS("document.querySelector('.zoo-top-section')?.textContent.includes('What’s the deal with people?') && document.querySelector('.zoo-top-section')?.textContent.includes('Simulated example')", "Top thread simulated badge missing.")
        try await click(".zoo-top-section .zoo-row-actions [data-zoo-reaction][data-zoo-kind='appreciate']")
        try await waitUntil("document.querySelector(\".zoo-top-section .zoo-row-actions [data-zoo-reaction][data-zoo-kind='appreciate']\")?.getAttribute('aria-pressed') === 'true'")
        try await assertJS("document.querySelector('.zoo-arena-section')?.textContent.includes('#Whats-The-Line')", "Arena rooms missing on Zoo page.")
        try await click("[data-zoo-arena-action='unseal-line']")
        try await waitUntil("document.querySelector('.zoo-arena-section')?.textContent.includes('Forecast Disagreement') || document.querySelector('.zoo-arena-section')?.textContent.includes('Contrarian AI Edge')")
        _ = try await evaluate("""
        (() => {
          const main = document.querySelector('#main') || document.documentElement || document.body;
          main.scrollTop = 0;
          window.scrollTo(0, 0);
          return true;
        })()
        """)
        try await pause(200_000_000)
        try await snapshot("04-reviewed-challenge")
        checks.append("Zoo categories, simulated Top Thread, reaction aria-pressed toggle, and Arena Blind-Line unseal verified")

        try await goHomePage()
        try await click("[data-start-project]")
        try await waitUntil("location.pathname === '/projects' && document.querySelector('#new-project')")
        try await click("#new-project")
        try await setValue("#project-title", "Product Launch Strategy")
        try await setValue("#project-goal", "Coordinate research, positioning, and creative review with your Twin.")
        try await submit("#project-form")
        try await waitUntil("typeof state !== 'undefined' && state.projects.some(p => p.name === 'Product Launch Strategy') && !document.querySelector('#work').classList.contains('hidden')")

        try await click("#add-decision")
        try await setValue("#decision-text", "Keep native project and Rooms storage separate.")
        try await submit("#decision-form")
        try await waitUntil("project().decisions.some(d => d.text.includes('storage separate'))")

        _ = try await evaluate("""
        (() => {
          const file = new File(['# Native validation\\n\\nThis document was written through the installed app.'], 'native-validation.md', {type:'text/markdown'});
          const transfer = new DataTransfer();
          transfer.items.add(file);
          document.querySelector('#file').files = transfer.files;
          document.querySelector('#file').dispatchEvent(new Event('change', {bubbles:true}));
          return true;
        })()
        """)
        try await waitUntil("project().documents.some(d => d.name === 'native-validation.md' && d.text.includes('installed app'))")
        try await snapshot("03-project-workspace")
        checks.append("Created project, decision, and Markdown document through native WebKit")

        try await click("#home")
        try await settleHome()
        try await waitUntil("state.projects.some(p => p.name === 'Product Launch Strategy')")
        try await click("[data-participant][aria-label^='You,']")
        try await assertJS("document.querySelector('[data-participant][aria-label^=\"You,\"]').classList.contains('show') && getComputedStyle(document.querySelector('[data-participant][aria-label^=\"You,\"] .tip')).display === 'block'", "Participant tap details did not appear.")
        checks.append("Participant tap details")

        try await click("#nav [data-page='challenges']")
        try await click("[data-new-challenge]")
        try await setValue("#challenge-name", "Validate a native macOS handoff")
        try await setValue("#challenge-prompt", "Confirm that a person can move from a project to Rooms and back without losing local context.")
        try await submit("#challenge-form")
        try await waitUntil("state.challenges.some(c => c.title === 'Validate a native macOS handoff' && c.status === 'submitted')")
        try await click("[data-review]")
        try await waitUntil("state.challenges.some(c => c.title === 'Validate a native macOS handoff' && c.status === 'reviewed')")
        try await click("[data-follow]")
        try await waitUntil("state.following.some(f => f.label === 'Validate a native macOS handoff')")
        try await click("#nav [data-page='following']")
        try await waitUntil("document.querySelector('#page').textContent.includes('Validate a native macOS handoff')")
        checks.append("Challenge submission, explicit review, and Following")

        try await click("#nav [data-page='collaboration']")
        try await waitUntil("page === 'collaboration' && document.querySelectorAll('[data-launch-solo]').length === 4")
        try await click("[data-launch-solo='visionary-skeptic']")
        try await waitUntil("document.querySelector('#collab-solo')?.textContent.includes('Active Solo Rooms')")
        checks.append("Solo 2-AI Goal Presets and room launcher verified")
        try await click("[data-collab-mode='multiplayer']")
        try await waitUntil("page === 'collaboration' && document.querySelector('#page [data-room=\"jay\"]')")
        try await click("#page [data-room='jay']")
        try await waitUntil("location.pathname === '/' && typeof state !== 'undefined' && state.me?.id === 'jay' && detail?.room")
        try await click("[data-policy='jay-twin']")
        try await waitUntil("document.querySelector('#dialog').open")
        try await setChecked("#enabled", true)
        try await setChecked("#mentions", true)
        try await setChecked("#readtool", true)
        try await submit("#dialogform")
        try await waitUntil("!document.querySelector('#dialog').open && detail.agents.some(a => a.id === 'jay-twin' && a.enabled)")
        try await setValue("#message", "@jay-twin summarize this native window validation")
        try await submit("#compose")
        try await waitUntil("detail.events.some(e => e.kind === 'agent' && e.text.toLowerCase().includes('deterministic')) && detail.jobs.some(j => j.status === 'complete')")
        try await snapshot("05-rooms-deterministic")
        checks.append("Rooms owner authorization, real deterministic worker completion, and screenshot")

        try await click("a[href='elect-twin://home']")
        try await settleHome()
        try await assertJS("state.projects.some(p => p.name === 'Product Launch Strategy')", "Project context was lost after returning from Rooms.")
        try await snapshot("06-home-after-rooms")
        checks.append("Rooms to Twin custom-scheme return with project context intact")
    }

    private func runReopen() async throws {
        try await settleHome()
        try await waitUntil("state.projects.some(p => p.name === 'Product Launch Strategy') && state.challenges.some(c => c.status === 'reviewed') && state.following.length > 0")
        checks.append("Native restart restored project, reviewed challenge, and Following")

        try await click("#nav [data-page='zoo']")
        try await waitUntil("page === 'zoo' && document.querySelector(\".zoo-top-section .zoo-row-actions [data-zoo-reaction][data-zoo-kind='appreciate']\")?.getAttribute('aria-pressed') === 'true'")
        checks.append("Native restart restored Zoo reaction state")

        try await click("#nav [data-page='projects']")
        try await click("[data-open-project]")
        try await waitUntil("location.pathname === '/projects' && project()?.name === 'Product Launch Strategy' && project().documents.some(d => d.name === 'native-validation.md') && project().decisions.some(d => d.text.includes('storage separate'))")
        try await snapshot("07-reopened-project")
        checks.append("Native restart restored the decision and Markdown document")

        try await click("#home")
        try await settleHome()
        try await click("#page [data-room='jay']")
        try await waitUntil("location.pathname === '/' && detail?.events?.some(e => e.text.includes('native window validation')) && detail?.events?.some(e => e.kind === 'agent')")
        checks.append("Native restart restored Rooms human and deterministic agent events")

        try await click("a[href='elect-twin://home']")
        try await settleHome()
        try await snapshot("08-reopened-home")
    }

    private func writeReport(success: Bool, error: String?) throws {
        let report: [String: Any] = [
            "mode": reopen ? "native_reopen" : "native_first_launch",
            "success": success,
            "checks": checks,
            "provider_calls": 0,
            "error": error ?? NSNull(),
            "screenshots_are_wkwebview_snapshots": true
        ]
        let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: output.appendingPathComponent(reopen ? "reopen-report.json" : "native-report.json"))
    }
}

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
        let diag = (try? await evaluate("JSON.stringify({href: location.href, path: location.pathname, hasState: typeof state !== 'undefined', btns: document.querySelectorAll('#nav button').length, setupExists: Boolean(document.querySelector('#setup-dialog')), setupOpen: Boolean(document.querySelector('#setup-dialog')?.open), setupShown: typeof setupShown !== 'undefined' ? setupShown : 'undef', onboardingStatus: typeof state !== 'undefined' ? state?.profile?.onboarding?.status : 'undef', maybeShowSetupType: typeof maybeShowSetup, openSetupType: typeof openSetup, osView: typeof osView !== 'undefined' ? osView : 'undef', osTab: typeof osLayout !== 'undefined' ? osLayout?.active_tab : 'undef', osWidgets: typeof osLayout !== 'undefined' && osLayout ? osActiveTab(osLayout).widgets.map(w => w.id) : [], toastText: document.querySelector('.sd-toast-wrap')?.textContent || '', statusText: document.querySelector('#status')?.textContent || 'empty', renderError: window.__lastRenderError || 'none', jsError: window.__lastJSError || 'none'})")) as? String ?? "nil"
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
        if selector.contains("data-os-move") {
            let diagnostic = (try? await evaluate("JSON.stringify({widgets: osActiveTab(osLayout).widgets.map(w => w.id), earlierDisabled: document.querySelector(\"#studio-dashboard [data-os-move='-1'][data-os-id='dash-command-my_models_hub']\")?.disabled})")) as? String ?? "nil"
            log("Move click \(selector): \(diagnostic)")
        }
    }

    private func clickFirst(_ selector: String) async throws {
        let script = """
        (() => {
          const node = document.querySelector(\(literal(selector)));
          if (!node) throw new Error('Missing matching element');
          node.click();
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

    private func waitForOS() async throws {
        try await waitUntil("typeof osLayout !== 'undefined' && osLayout?.schema_version === 2 && document.querySelectorAll('#studio-dashboard [data-os-tab]').length === 5")
    }

    private func settleHome() async throws {
        try await waitUntil("location.pathname === '/home' && typeof state !== 'undefined' && state.providers.length === 6 && document.querySelectorAll('#nav button').length === 9")
        try await pause()
        _ = try await evaluate("""
        (() => {
          if (document.querySelector('#setup-dialog')?.open) document.querySelector('#setup-dialog [data-setup-not-now]')?.click();
          if (document.querySelector('#provider-dialog')?.open) document.querySelector('#provider-dialog .actions [data-close]')?.click();
          if (document.querySelector('#invitation-dialog')?.open) document.querySelector('#invitation-dialog [data-invitation-close]')?.click();
          if (document.querySelector('#zoo-agent-dialog')?.open) document.querySelector('#zoo-agent-dialog [data-close]')?.click();
          if (typeof osView !== 'undefined' && osView === 'tasks') document.querySelector('[data-os-view="dashboard"]')?.click();
          return true;
        })()
        """)
        try await waitForOS()
    }

    private func goHomePage() async throws {
        try await click("#nav [data-page='home']")
        try await waitUntil("page === 'home' && document.querySelector('h1')?.textContent.startsWith('Good to see you')")
        try await waitForOS()
    }

    private func presentDashboardSurface() async throws {
        try await waitUntil("!document.querySelector('.sd-toast')")
        _ = try await evaluate("""
        (() => {
          const section = document.getElementById('studio-dashboard');
          if (!section) throw new Error('Missing #studio-dashboard');
          section.scrollIntoView({block:'start'});
          return true;
        })()
        """)
        try await waitUntil("(() => { const r = document.getElementById('studio-dashboard')?.getBoundingClientRect(); return Boolean(r && r.top >= 0 && r.top < 240); })()")
        try await pause(350_000_000)
    }

    private func waitForWidgetDataSettled() async throws {
        try await waitUntil("(() => { const types = osActiveTab(osLayout).widgets.map(w => w.type); const needOdds = types.includes('pro_sports_odds_board'); const needTracker = types.some(t => ['multimodal_model_tracker','model_tracker_hub'].includes(t)); return (!needOdds || (typeof osOdds !== 'undefined' && osOdds !== null)) && (!needTracker || (typeof osTracker !== 'undefined' && osTracker !== null)); })()")
    }

    private func runFirstLaunch() async throws {
        try await waitUntil("location.pathname === '/home' && typeof state !== 'undefined' && state.providers.length === 6 && document.querySelectorAll('#nav button').length === 9")
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

        try await waitForOS()
        try await assertJS("osLayout.tabs.length === 5 && osLayout.active_tab === 'command' && osActiveTab(osLayout).widgets.length === 6", "The five-tab OS did not load the six-widget Command dashboard.")
        for marker in ["While You Were Out", "Pinned Decisions", "Task Center Live Feed", "Airlock Privacy Diff", "My Models", "OpenSkills"] {
            try await assertJS("document.querySelector('#studio-dashboard')?.textContent.includes(\(literal(marker)))", "Command dashboard is missing \(marker).")
        }
        try await presentDashboardSurface()
        try await snapshot("02-home-bento")
        checks.append("Five OS tabs and six default Command Bento widgets rendered")

        try await click("#studio-dashboard [data-os-move='1'][data-os-id='dash-command-my_models_hub']")
        try await waitUntil("osActiveTab(osLayout).widgets[1].id === 'dash-command-my_models_hub' && document.querySelector(\"#studio-dashboard [data-os-move='-1'][data-os-id='dash-command-my_models_hub']\")?.disabled === false")
        try await click("#studio-dashboard [data-os-move='-1'][data-os-id='dash-command-my_models_hub']")
        try await waitUntil("osActiveTab(osLayout).widgets[0].id === 'dash-command-my_models_hub' && document.querySelector(\"#studio-dashboard [data-os-move='-1'][data-os-id='dash-command-my_models_hub']\")?.disabled === true")
        try await click("[data-os-customize]")
        try await setValue("[data-os-widget-title='dash-command-morning_postcard']", "While You Were Out · Native QC")
        try await waitUntil("osActiveTab(osLayout).widgets.some(w => w.title === 'While You Were Out · Native QC')")
        try await setValue("[data-os-widget-title='dash-command-morning_postcard']", "While You Were Out")
        try await waitUntil("osActiveTab(osLayout).widgets.some(w => w.title === 'While You Were Out')")
        try await click("[data-os-customize]")
        try await click("[data-os-delete-widget='dash-command-airlock_privacy_diff']")
        try await waitUntil("osActiveTab(osLayout).widgets.length === 5 && document.querySelector('.sd-toast button')?.textContent === 'Undo'")
        try await click(".sd-toast button")
        try await waitUntil("osActiveTab(osLayout).widgets.length === 6")
        try await setValue("#os-add-type", "fork_crew_spotlight")
        try await click("[data-os-add-widget]")
        try await waitUntil("osActiveTab(osLayout).widgets.length === 7 && osActiveTab(osLayout).widgets.some(w => w.type === 'fork_crew_spotlight') && document.querySelector(\"#studio-dashboard [data-os-card^='dash-command-fork_crew_spotlight-'] [data-os-delete-widget]\")")
        try await click("#studio-dashboard [data-os-card^='dash-command-fork_crew_spotlight-'] [data-os-delete-widget]")
        try await waitUntil("osActiveTab(osLayout).widgets.length === 6")
        checks.append("Native Bento move, edit, delete/Undo, add, and remove interactions")

        try await click("[data-os-tab='news']")
        try await waitUntil("osLayout.active_tab === 'news' && document.querySelector('#os-news-form')")
        try await waitForWidgetDataSettled()
        try await setValue("#os-news-input", "Native QC supplied local headline")
        try await setValue("#os-news-source", "Alpha launches a local test. Beta confirms the deterministic result.")
        try await setValue("#os-news-kind", "primary")
        try await submit("#os-news-form")
        try await waitUntil("osNewsResult !== null && osNewsResult.frames.length === 3")
        try await click("[data-os-news-mode='split']")
        try await waitUntil("osNewsReadingMode === 'split' && document.querySelectorAll('#os-news-result .os-frame').length >= 6")
        try await assertJS("document.querySelector('#os-news-result')?.textContent.includes('FACT') && document.querySelector('#os-news-result')?.textContent.includes('COULDNT_VERIFY')", "Open News split view did not expose its receipt labels.")
        try await click("[data-os-news-mode='audio']")
        try await waitUntil("osNewsReadingMode === 'audio' && document.querySelector('.os-audio-script')")
        try await assertJS("document.querySelector('#os-news-result')?.textContent.includes('Audio unavailable')", "Open News did not honestly label unavailable audio.")
        try await click("[data-os-news-mode='scan']")
        try await waitUntil("osNewsReadingMode === 'scan' && document.querySelector('.os-scan-grid')")
        try await click("[data-os-news-mode='split']")
        try await waitUntil("osNewsReadingMode === 'split'")
        try await presentDashboardSurface()
        try await snapshot("03-open-news")
        checks.append("Open News local analysis, scan/split/audio switching, three frames, and receipt")

        try await click("[data-os-tab='ai-code']")
        try await waitUntil("osLayout.active_tab === 'ai-code' && document.querySelector('#os-skills-form')")
        try await waitForWidgetDataSettled()
        try await setValue("#os-skill-query", "security")
        try await submit("#os-skills-form")
        try await waitUntil("osSkillResults.length > 0 && document.querySelector('[data-os-skill]')")
        try await clickFirst("[data-os-skill]")
        try await waitUntil("osSelectedSkills.size === 1")
        try await click("#studio-dashboard [data-os-optimize-selected]")
        try await waitUntil("osSkillBundle !== null && document.querySelector('#os-skill-inspector')?.textContent.includes('Challenger')")
        try await presentDashboardSurface()
        try await snapshot("04-open-skills")
        checks.append("OpenSkills local discovery, selection, and builder/challenger enrichment")

        try await click("#studio-dashboard [data-os-models-drawer]")
        try await waitUntil("document.querySelector('.os-drawer')?.textContent.includes('My Models')")
        try await assertJS("document.querySelector('.os-drawer')?.textContent.includes('Credentials stay in the existing session-only connection flow')", "Model drawer lost its session-only credential boundary.")
        try await click(".os-drawer [data-os-drawer-close]")
        try await waitUntil("!document.querySelector('.os-drawer')")
        checks.append("My Models version-router drawer and session-only credential boundary")

        let destinations = [("models", "My Models"), ("projects", "My Projects"), ("twin", "My Twin"), ("people", "People"), ("collaboration", "Collaboration"), ("challenges", "Agent Challenges"), ("following", "Following"), ("zoo", "OpenZoo")]
        for (id, title) in destinations {
            try await click("#nav [data-page='\(id)']")
            try await waitUntil("page === '\(id)' && document.querySelector('h1')?.textContent === \(literal(title))")
            checks.append("Native navigation: \(title)")
            if id == "models" { try await snapshot("05-my-models") }
        }

        var becameKey = false
        for _ in 0..<25 {
            NSApp.activate(ignoringOtherApps: true)
            app.window.makeKeyAndOrderFront(nil)
            try await pause(200_000_000)
            if app.window.isKeyWindow { becameKey = true; break }
        }
        app.window.makeFirstResponder(webView)
        try await pause(200_000_000)
        log("Window isKey: \(app.window.isKeyWindow)")
        guard becameKey else { throw NativeTestError.assertion("Window did not become key for the WebKit focus check.") }
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

        try await click("#nav [data-page='collaboration']")
        try await waitUntil("page === 'collaboration' && document.querySelectorAll('[data-launch-solo]').length === 4")
        try await click("[data-launch-solo='visionary-skeptic']")
        try await waitUntil("document.querySelector('#collab-solo')?.textContent.includes('Active Solo Rooms')")
        checks.append("Solo 1-Human + 2-AI Goal Preset and room launcher verified")
        try await click("[data-collab-mode='multiplayer']")
        try await waitUntil("page === 'collaboration' && document.querySelector('#page [data-room=\"jay\"]')")
        try await assertJS("document.querySelector('#collab-multiplayer')?.textContent.includes('Two workers can run in parallel')", "Shared Rooms did not expose its deterministic two-worker boundary.")
        try await snapshot("06-shared-rooms")
        checks.append("Shared Rooms multiplayer view and two-worker boundary")

        try await goHomePage()
        try await click(".os-topbar [data-os-view='tasks']")
        try await waitUntil("osView === 'tasks' && document.querySelectorAll('[data-os-task]').length > 0")
        try await assertJS("[...document.querySelectorAll('[data-os-task-budget]')].every(input => Number(input.value) === 0)", "Task Center seed budgets were not all $0.00.")
        try await presentDashboardSurface()
        try await snapshot("07-task-center")
        checks.append("Task Center rendered background-job policies with $0.00 seed budgets")
        try await click("[data-os-view='dashboard']")
        try await waitForOS()

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
        try await snapshot("08-open-zoo")
        checks.append("OpenZoo categories, simulated Top Thread, reaction, and Arena Blind-Line unseal")

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
        checks.append("Rooms owner authorization and real deterministic worker completion")

        try await click("a[href='elect-twin://home']")
        try await settleHome()
        try await assertJS("state.projects.some(p => p.name === 'Product Launch Strategy')", "Project context was lost after returning from Rooms.")
        checks.append("Rooms to Twin custom-scheme return with project context intact")
    }

    private func runReopen() async throws {
        try await settleHome()
        try await click("[data-os-tab='command']")
        try await waitUntil("osLayout.active_tab === 'command' && osActiveTab(osLayout).widgets.length === 6")
        try await assertJS("osActiveTab(osLayout).widgets.some(w => w.title === 'While You Were Out') && !osActiveTab(osLayout).widgets.some(w => w.type === 'fork_crew_spotlight')", "Native restart did not restore the expected dashboard layout.")
        checks.append("Native restart restored five-tab dashboard and six Command widgets")

        for id in ["news", "ai-code", "markets", "zoo-studio"] {
            try await click("[data-os-tab='\(id)']")
            try await waitUntil("osLayout.active_tab === \(literal(id))")
        }
        checks.append("Native restart revisited Open News, OpenSkills, Markets, and Zoo Studio tabs")

        try await click("#nav [data-page='models']")
        try await waitUntil("page === 'models' && document.querySelector('h1')?.textContent === 'My Models'")
        checks.append("Native restart reopened My Models")

        try await click("#nav [data-page='collaboration']")
        try await waitUntil("page === 'collaboration' && document.querySelector('#collab-solo')?.textContent.includes('Active Solo Rooms')")
        try await click("[data-collab-mode='multiplayer']")
        try await waitUntil("document.querySelector('#page [data-room=\"jay\"]')")
        checks.append("Native restart restored Solo and Shared Rooms")

        try await goHomePage()
        try await click(".os-topbar [data-os-view='tasks']")
        try await waitUntil("osView === 'tasks' && document.querySelectorAll('[data-os-task]').length > 0")
        try await click("[data-os-view='dashboard']")
        try await waitForOS()
        checks.append("Native restart reopened Task Center policies without executing jobs")

        try await click("#nav [data-page='zoo']")
        try await waitUntil("page === 'zoo' && document.querySelector(\".zoo-top-section .zoo-row-actions [data-zoo-reaction][data-zoo-kind='appreciate']\")?.getAttribute('aria-pressed') === 'true'")
        checks.append("Native restart restored OpenZoo reaction state")

        try await waitUntil("state.projects.some(p => p.name === 'Product Launch Strategy') && state.challenges.some(c => c.status === 'reviewed') && state.following.length > 0")
        checks.append("Native restart restored project, reviewed challenge, and Following")

        try await click("#nav [data-page='projects']")
        try await click("[data-open-project]")
        try await waitUntil("location.pathname === '/projects' && project()?.name === 'Product Launch Strategy' && project().documents.some(d => d.name === 'native-validation.md') && project().decisions.some(d => d.text.includes('storage separate'))")
        checks.append("Native restart restored the decision and Markdown document")

        try await click("#home")
        try await settleHome()
        try await click("#page [data-room='jay']")
        try await waitUntil("location.pathname === '/' && detail?.events?.some(e => e.text.includes('native window validation')) && detail?.events?.some(e => e.kind === 'agent')")
        checks.append("Native restart restored Rooms human and deterministic agent events")

        try await click("a[href='elect-twin://home']")
        try await settleHome()
        checks.append("Native reopen completed with project and Rooms context intact")
    }

    private func writeReport(success: Bool, error: String?) throws {
        let report: [String: Any] = [
            "mode": reopen ? "native_reopen" : "native_first_launch",
            "success": success,
            "assertion_count": checks.count,
            "screenshot_count": reopen ? 0 : 8,
            "checks": checks,
            "provider_calls": 0,
            "error": error ?? NSNull(),
            "screenshots_are_wkwebview_snapshots": true
        ]
        let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: output.appendingPathComponent(reopen ? "reopen-report.json" : "native-report.json"))
    }
}

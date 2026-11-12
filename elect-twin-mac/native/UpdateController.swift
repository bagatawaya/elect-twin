import AppKit
import Foundation

@MainActor
final class UpdateController: NSObject, NSMenuItemValidation {
    private let defaults: UserDefaults
    private let installedVersion: String
    private let channel: UpdateChannel
    private let architecture: String
    private let disabledForTest: Bool
    private var timer: Timer?
    private var fetch: UpdateFetch?
    private var wantsManualResult = false
    private var stopped = false
    private var checkItem: NSMenuItem?
    private var automaticItem: NSMenuItem?
    private var pendingUpdate: AvailableUpdate?
    private weak var window: NSWindow?

    private enum Key {
        static let automatic = "OpenTwinAutomaticallyCheckForUpdates"
        static let lastAttempt = "OpenTwinLastUpdateAttempt"
        static let skippedTag = "OpenTwinSkippedUpdateTag"
        static let notifiedTag = "OpenTwinNotifiedUpdateTag"
        static let notifiedDate = "OpenTwinLastUpdateNotification"
    }

    init(bundle: Bundle = .main, defaults: UserDefaults = .standard, disabledForTest: Bool = false) {
        self.defaults = defaults
        self.disabledForTest = disabledForTest
        installedVersion = bundle.object(forInfoDictionaryKey: "OpenTwinReleaseVersion") as? String
            ?? bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? ""
        channel = UpdateChannel(rawValue: bundle.object(forInfoDictionaryKey: "OpenTwinUpdateChannel") as? String ?? "stable") ?? .stable
        #if arch(arm64)
        architecture = "arm64"
        #else
        architecture = "x86_64"
        #endif
        super.init()
        if !disabledForTest { defaults.register(defaults: [Key.automatic: true]) }
    }

    func addMenuItems(to menu: NSMenu) {
        let check = menu.addItem(withTitle: "Check for Updates…", action: #selector(checkManually), keyEquivalent: "")
        check.target = self
        checkItem = check
        let automatic = menu.addItem(withTitle: "Automatically Check for Updates", action: #selector(toggleAutomatic), keyEquivalent: "")
        automatic.target = self
        automatic.toolTip = "Checks GitHub once a day while OpenTwin is running. No project data is sent."
        automaticItem = automatic
        syncMenu()
    }

    func start(window: NSWindow) {
        guard !disabledForTest, timer == nil else { return }
        self.window = window
        // Wait until the local engines are ready. This never delays app startup.
        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
        tick()
    }

    func stop() {
        stopped = true
        timer?.invalidate()
        timer = nil
        pendingUpdate = nil
        fetch?.cancel()
        fetch = nil
    }

    func validateMenuItem(_ menuItem: NSMenuItem) -> Bool { !disabledForTest && !stopped }

    private func syncMenu() {
        checkItem?.title = fetch == nil ? "Check for Updates…" : "Checking for Updates…"
        automaticItem?.state = defaults.bool(forKey: Key.automatic) ? .on : .off
        checkItem?.isEnabled = !disabledForTest && !stopped
        automaticItem?.isEnabled = !disabledForTest && !stopped
    }

    private func tick() {
        guard !stopped, defaults.bool(forKey: Key.automatic) else { return }
        presentPendingUpdate()
        guard UpdateSchedule.isDue(lastAttempt: defaults.object(forKey: Key.lastAttempt) as? Date, now: Date()) else { return }
        check(manual: false)
    }

    @objc private func toggleAutomatic() {
        defaults.set(!defaults.bool(forKey: Key.automatic), forKey: Key.automatic)
        if !defaults.bool(forKey: Key.automatic) { pendingUpdate = nil }
        syncMenu()
        tick()
    }

    @objc private func checkManually() { check(manual: true) }

    private func check(manual: Bool) {
        guard !disabledForTest, !stopped else { return }
        wantsManualResult = wantsManualResult || manual
        guard fetch == nil else { return } // Repeated clicks join the same request.
        defaults.set(Date(), forKey: Key.lastAttempt)
        let request = UpdateFetch()
        fetch = request
        syncMenu()
        request.start { [weak self] result in
          Task { @MainActor in
            guard let self, !self.stopped else { return }
            let manual = self.wantsManualResult
            self.wantsManualResult = false
            self.fetch = nil
            self.syncMenu()
            do {
                let data = try result.get()
                let update = try UpdateFeed.select(data, installed: self.installedVersion,
                    channel: self.channel, architecture: self.architecture)
                if let update {
                    if manual { self.pendingUpdate = nil; self.showUpdate(update) }
                    else if self.defaults.bool(forKey: Key.automatic),
                            UpdateNotificationPolicy.shouldNotify(tag: update.tag,
                                skippedTag: self.defaults.string(forKey: Key.skippedTag),
                                lastTag: self.defaults.string(forKey: Key.notifiedTag),
                                lastDate: self.defaults.object(forKey: Key.notifiedDate) as? Date, now: Date()) {
                        self.pendingUpdate = update
                        self.presentPendingUpdate()
                    }
                } else if manual {
                    self.showMessage("No newer compatible release found",
                        "Installed: \(self.installedVersion). Channel: \(self.channel.rawValue). GitHub has no newer matching macOS installer with a checksum sidecar in its 100 most recent releases.")
                }
            } catch {
                // Never interrupt local work because an automatic metadata check failed.
                if manual { self.showMessage("Could not check for updates", error.localizedDescription) }
            }
          }
        }
    }

    private func presentPendingUpdate() {
        guard let update = pendingUpdate, NSApp.isActive, let window,
              window.isVisible, window.attachedSheet == nil, NSApp.modalWindow == nil else { return }
        pendingUpdate = nil
        showUpdate(update)
    }

    private func showUpdate(_ update: AvailableUpdate) {
        defaults.set(update.tag, forKey: Key.notifiedTag)
        defaults.set(Date(), forKey: Key.notifiedDate)
        let alert = NSAlert()
        alert.messageText = "OpenTwin \(update.tag) is available"
        alert.informativeText = "You have \(installedVersion). Review the GitHub release and installation notes before downloading.\n\nThis checker does not verify Developer ID signatures or notarization. Current internal builds are ad-hoc signed. No update is downloaded or installed automatically."
        alert.addButton(withTitle: "Review Update…")
        alert.addButton(withTitle: "Later")
        alert.addButton(withTitle: "Skip This Version")
        switch alert.runModal() {
        case .alertFirstButtonReturn:
            if !NSWorkspace.shared.open(update.releaseURL) {
                showMessage("Could not open GitHub", "Open the OpenTwin GitHub Releases page in your browser to review this update.")
            }
        case .alertThirdButtonReturn: defaults.set(update.tag, forKey: Key.skippedTag)
        default: break
        }
    }

    private func showMessage(_ title: String, _ message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

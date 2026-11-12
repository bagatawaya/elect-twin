using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace ElectTwinWin;

internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);

        try
        {
            using var app = new ElectTwinApp(args);
            Application.Run(app.MainWindow);
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to start Elect Twin:\n\n{ex.Message}\n\n{ex.StackTrace}",
                "Elect Twin - Launch Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}

internal sealed class ElectTwinApp : IDisposable
{
    public Form MainWindow { get; }

    private readonly WebView2 _webView;
    private readonly HashSet<int> _allowedPorts = new();
    private readonly WindowsJobObject _jobObject;
    private readonly string _dataRoot;
    private Process? _roomsProcess;
    private Process? _twinProcess;
    private string? _homeUrl;
    private bool _isDisposed;

    public ElectTwinApp(string[] args)
    {
        _jobObject = new WindowsJobObject();
        _dataRoot = ResolveDataRoot(args);
        Directory.CreateDirectory(_dataRoot);

        MainWindow = new Form
        {
            Text = "Elect Twin - Internal test build · local workspace",
            Width = 1280,
            Height = 860,
            MinimumSize = new Size(920, 640),
            StartPosition = FormStartPosition.CenterScreen,
            BackColor = Color.FromArgb(248, 247, 244)
        };

        _webView = new WebView2
        {
            Dock = DockStyle.Fill
        };
        MainWindow.Controls.Add(_webView);

        ConfigureMenu();

        MainWindow.Load += async (_, _) => await InitializeAsync();
        MainWindow.FormClosed += (_, _) => Dispose();
    }

    private void ConfigureMenu()
    {
        var menuStrip = new MenuStrip();

        var appMenu = new ToolStripMenuItem("&App");
        appMenu.DropDownItems.Add("&About OpenTwin", null, (_, _) => ShowAbout());
        appMenu.DropDownItems.Add(new ToolStripSeparator());
        appMenu.DropDownItems.Add("E&xit", null, (_, _) => MainWindow.Close());

        var navMenu = new ToolStripMenuItem("&Navigate");
        var homeItem = new ToolStripMenuItem("&Home", null, (_, _) => NavigateHome())
        { ShortcutKeys = Keys.Control | Keys.Shift | Keys.H };
        navMenu.DropDownItems.Add(homeItem);
        var backItem = new ToolStripMenuItem("&Back", null, (_, _) => { if (_webView.CanGoBack) _webView.GoBack(); })
        { ShortcutKeys = Keys.Alt | Keys.Left };
        navMenu.DropDownItems.Add(backItem);
        var forwardItem = new ToolStripMenuItem("&Forward", null, (_, _) => { if (_webView.CanGoForward) _webView.GoForward(); })
        { ShortcutKeys = Keys.Alt | Keys.Right };
        navMenu.DropDownItems.Add(forwardItem);
        var reloadItem = new ToolStripMenuItem("&Reload", null, (_, _) => _webView.Reload())
        { ShortcutKeys = Keys.Control | Keys.R };
        navMenu.DropDownItems.Add(reloadItem);

        menuStrip.Items.Add(appMenu);
        menuStrip.Items.Add(navMenu);
        MainWindow.MainMenuStrip = menuStrip;
        MainWindow.Controls.Add(menuStrip);
    }

    private void ShowAbout()
    {
        MessageBox.Show(
            "Elect Twin 0.4.0 (build 2026111104)\n\n" +
            "A private human-and-agent collaboration workspace and Agent Zoo.\n\n" +
            "• Engine: Python 3.12 (standalone loopback runtime)\n" +
            "• Rooms: Pure Python deterministic coordination engine\n" +
            "• Shell: C# / .NET 8 with Microsoft Edge WebView2\n" +
            "• Security: Localhost binding (127.0.0.1) & Job Object process lifecycle\n\n" +
            "Data Root: " + _dataRoot,
            "About Elect Twin",
            MessageBoxButtons.OK,
            MessageBoxIcon.Information);
    }

    private void NavigateHome()
    {
        if (!string.IsNullOrEmpty(_homeUrl))
        {
            _webView.Source = new Uri(_homeUrl);
        }
    }

    private string ResolveDataRoot(string[] args)
    {
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--data-root" && !string.IsNullOrWhiteSpace(args[i + 1]))
            {
                return Path.GetFullPath(args[i + 1]);
            }
        }
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(localAppData, "ElectTwin");
    }

    private async Task InitializeAsync()
    {
        try
        {
            var appDir = AppDomain.CurrentDomain.BaseDirectory;
            var twinExe = FindExecutable(appDir, "twin-server.exe", Path.Combine("Runtime", "twin-server.exe"));
            var roomsExe = FindExecutable(appDir, "rooms-server.exe", Path.Combine("Rooms", "rooms-server.exe"));

            var twinData = Path.Combine(_dataRoot, "projects.sqlite3");
            var zooData = Path.Combine(_dataRoot, "zoo.sqlite3");
            var roomsData = Path.Combine(_dataRoot, "rooms.sqlite3");

            // 1. Launch Rooms Engine
            var (roomsProc, roomsUrls) = StartRooms(roomsExe, roomsData);
            _roomsProcess = roomsProc;
            _jobObject.AddProcess(roomsProc);

            var jayUrl = roomsUrls["jay"];
            var alexUrl = roomsUrls["alex"];
            RecordPortFromUrl(jayUrl);
            RecordPortFromUrl(alexUrl);

            // 2. Launch Twin Engine
            var (twinProc, twinUrl) = StartTwin(twinExe, twinData, zooData, jayUrl, alexUrl);
            _twinProcess = twinProc;
            _jobObject.AddProcess(twinProc);
            RecordPortFromUrl(twinUrl);

            _homeUrl = twinUrl;

            // 3. Initialize WebView2
            var userDataFolder = Path.Combine(_dataRoot, "WebView2Data");
            var env = await CoreWebView2Environment.CreateAsync(null, userDataFolder);
            await _webView.EnsureCoreWebView2Async(env);

            _webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
            _webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
            _webView.CoreWebView2.Settings.IsZoomControlEnabled = true;

            // Navigation security policy
            _webView.CoreWebView2.NavigationStarting += HandleNavigationStarting;

            _webView.Source = new Uri(_homeUrl);
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Initialization Error: {ex.Message}",
                "Elect Twin Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private void HandleNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs e)
    {
        if (Uri.TryCreate(e.Uri, UriKind.Absolute, out var uri))
        {
            // Custom scheme handling
            if (uri.Scheme.Equals("elect-twin", StringComparison.OrdinalIgnoreCase))
            {
                e.Cancel = true;
                if (uri.Host.Equals("home", StringComparison.OrdinalIgnoreCase) && !string.IsNullOrEmpty(_homeUrl))
                {
                    _webView.Source = new Uri(_homeUrl);
                }
                else if (uri.Host.Equals("zoo", StringComparison.OrdinalIgnoreCase) && !string.IsNullOrEmpty(_homeUrl))
                {
                    _webView.Source = new Uri(_homeUrl.TrimEnd('/') + "/#zoo");
                }
                return;
            }

            // Loopback restriction
            if (uri.Host == "127.0.0.1" || uri.Host.Equals("localhost", StringComparison.OrdinalIgnoreCase))
            {
                if (_allowedPorts.Contains(uri.Port))
                {
                    return; // Allowed loopback navigation
                }
            }

            // External URLs: cancel and open in external system browser
            e.Cancel = true;
            try
            {
                Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Failed to open external link: {ex.Message}");
            }
        }
    }

    private void RecordPortFromUrl(string url)
    {
        if (Uri.TryCreate(url, UriKind.Absolute, out var uri))
        {
            _allowedPorts.Add(uri.Port);
        }
    }

    private string FindExecutable(string appDir, string directName, string relativeName)
    {
        var p1 = Path.Combine(appDir, directName);
        if (File.Exists(p1)) return p1;

        var p2 = Path.Combine(appDir, relativeName);
        if (File.Exists(p2)) return p2;

        // Fallback for development: check current directory or PATH
        if (File.Exists(directName)) return Path.GetFullPath(directName);

        throw new FileNotFoundException($"Cannot locate required engine executable: {directName} or {relativeName}");
    }

    private (Process process, Dictionary<string, string> urls) StartRooms(string exePath, string dataPath)
    {
        var psi = new ProcessStartInfo
        {
            FileName = exePath,
            Arguments = $"--port 0 --data \"{dataPath}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };

        var proc = Process.Start(psi) ?? throw new InvalidOperationException("Failed to launch Rooms server");
        var readyLine = ReadStdoutLineWithTimeout(proc, 20);

        using var doc = JsonDocument.Parse(readyLine);
        var root = doc.RootElement;
        if (!root.GetProperty("ready").GetBoolean())
        {
            throw new InvalidOperationException("Rooms server indicated not ready");
        }

        var urls = new Dictionary<string, string>();
        var urlsElement = root.GetProperty("urls");
        foreach (var prop in urlsElement.EnumerateObject())
        {
            urls[prop.Name] = prop.Value.GetString() ?? "";
        }

        return (proc, urls);
    }

    private (Process process, string url) StartTwin(string exePath, string twinData, string zooData, string jayUrl, string alexUrl)
    {
        var psi = new ProcessStartInfo
        {
            FileName = exePath,
            Arguments = $"--native --port 0 --data \"{twinData}\" --zoo-data \"{zooData}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        psi.Environment["ELECT_TWIN_ROOMS_JAY"] = jayUrl;
        psi.Environment["ELECT_TWIN_ROOMS_ALEX"] = alexUrl;

        var proc = Process.Start(psi) ?? throw new InvalidOperationException("Failed to launch Twin server");
        var readyLine = ReadStdoutLineWithTimeout(proc, 20);

        using var doc = JsonDocument.Parse(readyLine);
        var root = doc.RootElement;
        if (!root.GetProperty("ready").GetBoolean())
        {
            throw new InvalidOperationException("Twin server indicated not ready");
        }

        var url = root.GetProperty("url").GetString() ?? throw new InvalidOperationException("Missing twin url");
        return (proc, url);
    }

    private string ReadStdoutLineWithTimeout(Process process, int timeoutSeconds)
    {
        var outputTask = Task.Run(() => process.StandardOutput.ReadLine());
        if (!outputTask.Wait(TimeSpan.FromSeconds(timeoutSeconds)))
        {
            try { process.Kill(); } catch { }
            throw new TimeoutException($"Engine startup timed out after {timeoutSeconds}s");
        }
        var line = outputTask.Result;
        if (string.IsNullOrEmpty(line))
        {
            var err = process.StandardError.ReadToEnd();
            throw new InvalidOperationException($"Engine exited without ready line. Stderr:\n{err}");
        }
        return line;
    }

    public void Dispose()
    {
        if (_isDisposed) return;
        _isDisposed = true;

        try { _twinProcess?.Kill(); } catch { }
        try { _roomsProcess?.Kill(); } catch { }
        _jobObject.Dispose();
        _webView.Dispose();
        MainWindow.Dispose();
    }
}

/// <summary>
/// Safe Win32 Job Object wrapper ensuring all spawned child processes terminate
/// automatically when the main host process closes, crashes, or is killed.
/// </summary>
internal sealed class WindowsJobObject : IDisposable
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string? lpName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(
        IntPtr hJob,
        int JobObjectInfoClass,
        IntPtr lpJobObjectInfo,
        uint cbJobObjectInfoLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    private const int JobObjectExtendedLimitInformation = 9;
    private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;

    [StructLayout(LayoutKind.Sequential)]
    private struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryLimit;
        public UIntPtr PeakJobMemoryLimit;
    }

    private IntPtr _jobHandle;

    public WindowsJobObject()
    {
        _jobHandle = CreateJobObject(IntPtr.Zero, null);
        if (_jobHandle == IntPtr.Zero) return;

        var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            BasicLimitInformation = new JOBOBJECT_BASIC_LIMIT_INFORMATION
            {
                LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            }
        };

        var length = (uint)Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
        var ptr = Marshal.AllocHGlobal((int)length);
        try
        {
            Marshal.StructureToPtr(info, ptr, false);
            SetInformationJobObject(_jobHandle, JobObjectExtendedLimitInformation, ptr, length);
        }
        finally
        {
            Marshal.FreeHGlobal(ptr);
        }
    }

    public void AddProcess(Process process)
    {
        if (_jobHandle != IntPtr.Zero && !process.HasExited)
        {
            AssignProcessToJobObject(_jobHandle, process.Handle);
        }
    }

    public void Dispose()
    {
        if (_jobHandle != IntPtr.Zero)
        {
            CloseHandle(_jobHandle);
            _jobHandle = IntPtr.Zero;
        }
    }
}

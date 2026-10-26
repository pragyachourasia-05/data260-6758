# HW7 report screenshots: runs each step with a name banner and saves the capture to
# reports\hw07\screenshots\<id>.png. Terminal steps capture automatically with -Auto. Run from the repository root in a maximized PowerShell window:
#     powershell -ExecutionPolicy Bypass -File code\take_hw07_screenshots.ps1
#     powershell -ExecutionPolicy Bypass -File code\take_hw07_screenshots.ps1 -Only 2.1,4.2   # redo some
param([string[]]$Only, [switch]$Auto)  # -Auto: capture each terminal step after 2 s, no key presses

$ErrorActionPreference = "Stop"
$Name = "Pragya Chourasia"
$Root = Split-Path $PSScriptRoot -Parent
$Py = Join-Path $Root "venv\Scripts\python.exe"
$Out = Join-Path $Root "reports\hw07\screenshots"
New-Item -ItemType Directory -Force $Out | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$Host.UI.RawUI.WindowTitle = "$Name - DATA-260 HW7 - SID 6758"

Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class HwShot {
  public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int size);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr p);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  // First visible top-level window whose title starts with the given prefix.
  public static IntPtr FindByTitle(string prefix) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, p) => {
      if (!IsWindowVisible(h)) return true;
      var sb = new System.Text.StringBuilder(512);
      GetWindowText(h, sb, 512);
      if (sb.ToString().StartsWith(prefix)) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
"@
[void][HwShot]::SetProcessDPIAware()

# Find this terminal by the window title set above (works for Windows Terminal and the
# classic console). Never guess from "whatever is in front", which can be another app.
function Get-TermHwnd {
    Start-Sleep -Milliseconds 300
    return [HwShot]::FindByTitle("$Name - DATA-260 HW7")
}

function Save-Capture([string]$Id, [switch]$FullScreen) {
    if ($FullScreen) {
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $x = $b.X; $y = $b.Y; $w = $b.Width; $h = $b.Height
    } else {
        $TermHwnd = Get-TermHwnd
        if ($TermHwnd -eq [IntPtr]::Zero) {
            Write-Host "  Could not find the window titled '$Name - DATA-260 HW6'. Run this script in its own PowerShell window." -ForegroundColor Red
            return $null
        }
        [void][HwShot]::ShowWindow($TermHwnd, 3)   # restore + maximize (a background launch can start minimized)
        [void][HwShot]::SetForegroundWindow($TermHwnd)
        Start-Sleep -Milliseconds 900
        $r = New-Object HwShot+RECT
        [void][HwShot]::DwmGetWindowAttribute($TermHwnd, 9, [ref]$r, 16)
        $x = $r.Left; $y = $r.Top; $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
    }
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
    $path = Join-Path $Out "$Id.png"
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return $path
}

function Show-Banner([string]$Id, [string]$Title) {
    Clear-Host
    Write-Host ("=" * 100) -ForegroundColor Cyan
    Write-Host ("  {0}  |  DATA-260 HW7  |  SID4 6758  |  {1}" -f $Name, (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Cyan
    Write-Host ("  Screenshot {0}: {1}" -f $Id, $Title) -ForegroundColor Yellow
    Write-Host ("=" * 100) -ForegroundColor Cyan
}

$Steps = @(
    @{ Id = "1.1"; Kind = "terminal"; Title = "Part 1 POST /auth/login: valid -> JWT, invalid -> 401" },
    @{ Id = "1.2"; Kind = "terminal"; Title = "Part 1 GET /auth/me without a token -> 401" },
    @{ Id = "1.2b"; Kind = "terminal"; Title = "Part 1 GET /auth/me with an invalid or expired token -> 401" },
    @{ Id = "1.3"; Kind = "terminal"; Title = "Part 1 create: reader -> 403, writer -> 201" },
    @{ Id = "1.4"; Kind = "terminal"; Title = "Part 1 delete: writer -> 403, moderator -> 200" },
    @{ Id = "1.5"; Kind = "terminal"; Title = "Part 1 list/read with a valid token -> 200" },
    @{ Id = "2.A"; Kind = "terminal"; Title = "Part 2 task A: search, then detail-lookup the first result" },
    @{ Id = "2.B"; Kind = "terminal"; Title = "Part 2 task B: aggregate question, then a supporting example" },
    @{ Id = "2.C"; Kind = "terminal"; Title = "Part 2 task C: compare two listings (search + two detail lookups)" },
    @{ Id = "2.E"; Kind = "terminal"; Title = "Part 2 error recovery: nonexistent listing id" },
    @{ Id = "6.1"; Kind = "terminal"; Title = "Part 6 glob -> search -> read integration + 10-command safety gate" }
)
if ($Only) {
    # "-Only 1.1,1.2" arrives as one string when run with "powershell -File", so split it.
    $ids = $Only | ForEach-Object { $_ -split "[,\s]+" } | Where-Object { $_ }
    $Steps = $Steps | Where-Object { $ids -contains $_.Id }
    if (-not $Steps) { Write-Host "No step matches -Only $($Only -join ','). Valid ids are the Id values in `$Steps" -ForegroundColor Red; exit 1 }
}

foreach ($s in $Steps) {
    while ($true) {
        Show-Banner $s.Id $s.Title
        if ($s.Kind -eq "browser") {
            Start-Process $s.Url
            Write-Host ""
            Write-Host "  Opened $($s.Url) in your browser. Maximize it. Optionally send one message such as" -ForegroundColor Green
            Write-Host "  'What do you remember about me?' and wait for the reply (about 30-60 s)." -ForegroundColor Green
            Write-Host "  Then come back here, press Enter, and switch to the browser within 6 seconds." -ForegroundColor Green
            $key = Read-Host "  [Enter] full-screen capture in 6 s   [s] skip"
            if ($key -eq "s") { break }
            for ($i = 6; $i -ge 1; $i--) { Write-Host "  capturing in $i ..."; Start-Sleep 1 }
            $p = Save-Capture $s.Id -FullScreen
        } else {
            & $Py (Join-Path $Root "code\hw07_screenshot_steps.py") $s.Id
            Write-Host ""
            if ($Auto) { Start-Sleep 2; $key = "" }
            else { $key = Read-Host "  [Enter] capture this window   [r] run again   [s] skip" }
            if ($key -eq "s") { break }
            if ($key -eq "r") { continue }
            $p = Save-Capture $s.Id
        }
        if (-not $p) { Read-Host "  Nothing saved. Press Enter to try this step again"; continue }
        Write-Host "  saved $p" -ForegroundColor Green
        Start-Sleep 1
        break
    }
}
Write-Host ""
Write-Host "Done. Screenshots are in $Out" -ForegroundColor Cyan
Get-ChildItem $Out -Filter *.png | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize

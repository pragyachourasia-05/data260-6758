# HW11: one terminal screenshot of my self-check
param([string]$Only = "")
# HW11 screenshots: opens terminal windows titled with my name, runs the commands and saves each window.
#     powershell -File code\hw11_screenshots.ps1
$ErrorActionPreference = "Continue"
$Root = "C:\SJSU Assignments\Agentic AI\Assignment_1"
Set-Location $Root
$Name = "Pragya Chourasia"
$Shots = Join-Path $Root "reports\hw11\screenshots"; New-Item -ItemType Directory -Force $Shots | Out-Null
$Tmp = Join-Path $env:TEMP "hw11_windows"; New-Item -ItemType Directory -Force $Tmp | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Hw11Shot {
  public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int size);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr p);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  public static IntPtr FindByTitle(string title) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, p) => { if (!IsWindowVisible(h)) return true; var sb = new System.Text.StringBuilder(512);
      GetWindowText(h, sb, 512); if (sb.ToString().StartsWith(title)) { found = h; return false; } return true; }, IntPtr.Zero);
    return found;
  }
}
"@
[void][Hw11Shot]::SetProcessDPIAware()
$Opened = @()

function Open-Window([string]$Label, [string]$Dir, [string[]]$Commands) {
    $file = Join-Path $Tmp ("{0}.ps1" -f ($Label -replace "[^A-Za-z0-9]", "_"))
    $lines = @(
        "`$Host.UI.RawUI.WindowTitle = '$Name - DATA-260 HW11 - $Label'",
        "& '$Root\venv\Scripts\Activate.ps1'",
        "Set-Location '$Dir'",
        "Start-Sleep 2",
        "Clear-Host"
    )
    foreach ($c in $Commands) {
        $shown = $c -replace "'", "''"
        $lines += "Write-Host 'PS $Dir> $shown' -ForegroundColor Gray"
        $lines += $c
        $lines += "Write-Host ''"
    }
    Set-Content -Path $file -Value $lines -Encoding UTF8
    $script:Opened += Start-Process conhost.exe -ArgumentList "powershell.exe -NoExit -NoLogo -File `"$file`"" -PassThru
    # maximize before any output, so the console shows the output from the top
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 300
        $h = [Hw11Shot]::FindByTitle("$Name - DATA-260 HW11 - $Label")
        if ($h -ne [IntPtr]::Zero) { [void][Hw11Shot]::ShowWindow($h, 3); break }
    }
}

function Save-Shot([string]$Label, [string]$Id) {
    $h = [IntPtr]::Zero
    for ($i = 0; $i -lt 20 -and $h -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 500; $h = [Hw11Shot]::FindByTitle("$Name - DATA-260 HW11 - $Label") }
    if ($h -eq [IntPtr]::Zero) { Write-Host "window not found: $Label"; return }
    # minimize then restore, so the window comes to the front even when another window has focus
    [void][Hw11Shot]::ShowWindow($h, 6); Start-Sleep -Milliseconds 400
    [void][Hw11Shot]::ShowWindow($h, 9); [void][Hw11Shot]::ShowWindow($h, 3); [void][Hw11Shot]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 1500
    $r = New-Object Hw11Shot+RECT; [void][Hw11Shot]::DwmGetWindowAttribute($h, 9, [ref]$r, 16)
    $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
    $bmp.Save((Join-Path $Shots "$Id.png"), [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
    Write-Host "saved $Id.png"
}

function Close-Windows { foreach ($p in $script:Opened) { taskkill /PID $p.Id /T /F 2>&1 | Out-Null }; $script:Opened = @() }

function Shot([string]$Label, [string]$Id, [string[]]$Commands, [int]$Wait) {
    if ($Only -and ($Only -split "," ) -notcontains $Id) { return }
    Open-Window $Label $Root $Commands
    Start-Sleep $Wait; Save-Shot $Label $Id; Close-Windows
}


Shot "Verify" "5.1_verify" @('python verify_hw11.py *> $null', 'python code/hw11_show.py') 40

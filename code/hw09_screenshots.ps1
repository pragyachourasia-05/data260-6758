# Retake only some: -Only "1.2_counter,5.1_verify"
param([string]$Only = "")
# HW9 screenshots: opens terminal windows titled with my name, runs the commands and saves each window.
#     powershell -File code\hw09_screenshots.ps1
$ErrorActionPreference = "Continue"
$Root = "C:\SJSU Assignments\Agentic AI\Assignment_1"
Set-Location $Root
$Name = "Pragya Chourasia"
$Shots = Join-Path $Root "reports\hw09\screenshots"; New-Item -ItemType Directory -Force $Shots | Out-Null
$Tmp = Join-Path $env:TEMP "hw09_windows"; New-Item -ItemType Directory -Force $Tmp | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Hw9Shot {
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
[void][Hw9Shot]::SetProcessDPIAware()
$Opened = @()

function Open-Window([string]$Label, [string]$Dir, [string[]]$Commands) {
    $file = Join-Path $Tmp ("{0}.ps1" -f ($Label -replace "[^A-Za-z0-9]", "_"))
    $lines = @(
        "`$Host.UI.RawUI.WindowTitle = '$Name - DATA-260 HW9 - $Label'",
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
        $h = [Hw9Shot]::FindByTitle("$Name - DATA-260 HW9 - $Label")
        if ($h -ne [IntPtr]::Zero) { [void][Hw9Shot]::ShowWindow($h, 3); break }
    }
}

function Save-Shot([string]$Label, [string]$Id) {
    $h = [IntPtr]::Zero
    for ($i = 0; $i -lt 20 -and $h -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 500; $h = [Hw9Shot]::FindByTitle("$Name - DATA-260 HW9 - $Label") }
    if ($h -eq [IntPtr]::Zero) { Write-Host "window not found: $Label"; return }
    # minimize then restore, so the window comes to the front even when another window has focus
    [void][Hw9Shot]::ShowWindow($h, 6); Start-Sleep -Milliseconds 400
    [void][Hw9Shot]::ShowWindow($h, 9); [void][Hw9Shot]::ShowWindow($h, 3); [void][Hw9Shot]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 1500
    $r = New-Object Hw9Shot+RECT; [void][Hw9Shot]::DwmGetWindowAttribute($h, 9, [ref]$r, 16)
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

Shot "Docker" "1.1_containers" @('docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"') 6

Shot "Counter" "1.2_counter" @('python backend/run_hw09_counter.py') 25

Shot "Redis keys" "1.3_redis" @('docker exec s6758_redis redis-cli GET s6758:views:listing:4', 'docker exec s6758_redis redis-cli --scan --pattern ''s6758*''', 'docker exec s6758_redis redis-cli FT.INFO s6758:idx:semantic | Select-String COSINE,VECTOR') 8
Shot "Semantic cache" "2.1_semantic" @('python code/hw09_show.py part2') 5

Shot "Cache log" "2.2_cache_log" @('python code/hw09_show.py log') 5

Shot "Sweep" "3.1_sweep" @('python code/hw09_show.py sweep') 5

Shot "False hit" "3.2_false_hit" @('python code/hw09_show.py falsehit') 5

Shot "Stale test" "3.3_stale" @('python code/hw09_show.py stale') 5

Shot "Revision" "4.1_revision" @('python code/hw09_show.py revision') 5

Shot "Lesson reuse" "4.2_lesson" @('python code/hw09_show.py lesson') 5

Shot "Training" "4.3_training" @('python code/hw09_show.py training') 5

Shot "Validation" "4.4_validation" @('python code/hw09_show.py validation') 5

Shot "Test results" "4.5_test" @('python code/hw09_show.py test') 5

Shot "Lessons" "4.6_lessons" @('python code/hw09_show.py lessons') 5

Shot "Verify" "5.1_verify" @('python verify_hw09.py *> $null', 'python code/hw09_show.py verify') 150


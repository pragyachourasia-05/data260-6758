# Retake only some: -Only "4.1_trace_miss,D1_summary"
param([string]$Only = "")
# HW10 screenshots: opens terminal windows titled with my name, runs the commands and saves each window.
#     powershell -File code\hw10_screenshots.ps1
$ErrorActionPreference = "Continue"
$Root = "C:\SJSU Assignments\Agentic AI\Assignment_1"
Set-Location $Root
$Name = "Pragya Chourasia"
$Shots = Join-Path $Root "reports\hw10\screenshots"; New-Item -ItemType Directory -Force $Shots | Out-Null
$Tmp = Join-Path $env:TEMP "hw10_windows"; New-Item -ItemType Directory -Force $Tmp | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Hw10Shot {
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
[void][Hw10Shot]::SetProcessDPIAware()
$Opened = @()

function Open-Window([string]$Label, [string]$Dir, [string[]]$Commands) {
    $file = Join-Path $Tmp ("{0}.ps1" -f ($Label -replace "[^A-Za-z0-9]", "_"))
    $lines = @(
        "`$Host.UI.RawUI.WindowTitle = '$Name - DATA-260 HW10 - $Label'",
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
        $h = [Hw10Shot]::FindByTitle("$Name - DATA-260 HW10 - $Label")
        if ($h -ne [IntPtr]::Zero) { [void][Hw10Shot]::ShowWindow($h, 3); break }
    }
}

function Save-Shot([string]$Label, [string]$Id) {
    $h = [IntPtr]::Zero
    for ($i = 0; $i -lt 20 -and $h -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 500; $h = [Hw10Shot]::FindByTitle("$Name - DATA-260 HW10 - $Label") }
    if ($h -eq [IntPtr]::Zero) { Write-Host "window not found: $Label"; return }
    # minimize then restore, so the window comes to the front even when another window has focus
    [void][Hw10Shot]::ShowWindow($h, 6); Start-Sleep -Milliseconds 400
    [void][Hw10Shot]::ShowWindow($h, 9); [void][Hw10Shot]::ShowWindow($h, 3); [void][Hw10Shot]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 1500
    $r = New-Object Hw10Shot+RECT; [void][Hw10Shot]::DwmGetWindowAttribute($h, 9, [ref]$r, 16)
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


# Dashboard: a real Edge window with its own temporary profile; only that window is touched.
$Edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$EdgeProfile = Join-Path $env:TEMP "hw10_edge_profile"
Add-Type @"
using System; using System.Runtime.InteropServices;
public class EdgeWin {
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@
function Dash([string]$Id, [string]$Query, [int]$Wait = 14) {
    if ($Only -and ($Only -split ",") -notcontains $Id) { return }
    Remove-Item $EdgeProfile -Recurse -Force -ErrorAction SilentlyContinue  # fresh profile: no restore bubble, no first-run pages
    $p = Start-Process -FilePath $Edge -ArgumentList "--user-data-dir=`"$EdgeProfile`"", "--no-first-run", "--no-default-browser-check",
        "--disable-extensions", "--disable-sync", "--hide-crash-restore-bubble", "--app=http://localhost:8459/?$Query" -PassThru
    $h = [IntPtr]::Zero
    for ($i = 0; $i -lt 40 -and $h -eq [IntPtr]::Zero; $i++) {
        Start-Sleep -Milliseconds 500
        $cand = [Hw10Shot]::FindByTitle("s6758 operations - HW10")
        if ($cand -ne [IntPtr]::Zero) {
            $owner = [uint32]0; [void][EdgeWin]::GetWindowThreadProcessId($cand, [ref]$owner)
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$owner").CommandLine
            if ($cmd -like "*hw10_edge_profile*") { $h = $cand }
        }
    }
    if ($h -eq [IntPtr]::Zero) { Write-Host "dashboard window not found: $Id"; Stop-EdgeProfile; return }
    [void][Hw10Shot]::ShowWindow($h, 3); Start-Sleep $Wait
    [void][Hw10Shot]::ShowWindow($h, 6); Start-Sleep -Milliseconds 400
    [void][Hw10Shot]::ShowWindow($h, 9); [void][Hw10Shot]::ShowWindow($h, 3); [void][Hw10Shot]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 1500
    $r = New-Object Hw10Shot+RECT; [void][Hw10Shot]::DwmGetWindowAttribute($h, 9, [ref]$r, 16)
    $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
    $bmp.Save((Join-Path $Shots "$Id.png"), [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
    Write-Host "saved $Id.png"
    Stop-EdgeProfile
}
function Stop-EdgeProfile {
    Get-CimInstance Win32_Process -Filter "name='msedge.exe'" | Where-Object { $_.CommandLine -like "*hw10_edge_profile*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep 2
}

Shot "Docker" "1.1_containers" @('docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"') 6
Shot "Evaluator record" "2.1_eval_record" @('python code/hw10_show.py eval') 5
Shot "Evaluation summary" "2.2_eval_summary" @('python code/hw10_show.py evalsummary') 5
Shot "Judge validation" "3.1_judge" @('python code/hw10_show.py judge') 5
Shot "Trace cache miss" "4.1_trace_miss" @('python code/hw10_show.py trace cache_miss') 5
Shot "Trace cache hit" "4.2_trace_hit" @('python code/hw10_show.py trace cache_hit') 5
Shot "Trace failed" "4.3_trace_failed" @('python code/hw10_show.py trace failed') 5
Shot "Latency" "4.4_latency" @('python backend/run_hw10.py report') 5
Shot "Verify" "5.1_verify" @('python verify_hw10.py *> $null', 'python code/hw10_show.py verify') 150
Dash "D1_summary" "page=Summary"
Dash "D2_evaluation" "page=Evaluation"
Dash "D3_judge" "page=Evaluation&section=judge"
Dash "D4_trace_miss" "page=Trace%20lookup&trace=31a611af-e140-4d27-9e17-a5c4ef6a2a7c"
Dash "D5_trace_hit" "page=Trace%20lookup&trace=0eefeba3-9061-4adc-81fa-63dcb28536c0"
Dash "D6_trace_failed" "page=Trace%20lookup&trace=11b0c62f-4d58-49ab-bcf7-055874b9fc60"

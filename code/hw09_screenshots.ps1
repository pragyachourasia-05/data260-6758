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

Open-Window "Docker" $Root @('docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"')
Start-Sleep 6; Save-Shot "Docker" "1.1_containers"; Close-Windows

Open-Window "Counter" $Root @('python backend/run_hw09_counter.py')
Start-Sleep 14; Save-Shot "Counter" "1.2_counter"; Close-Windows

Open-Window "Redis keys" $Root @('docker exec s6758_redis redis-cli GET s6758:views:listing:4', 'docker exec s6758_redis redis-cli --scan --pattern ''s6758*''', 'docker exec s6758_redis redis-cli FT.INFO s6758:idx:semantic | Select-String -Pattern ''index_name|s6758:idx|COSINE|VECTOR'' ')
Start-Sleep 8; Save-Shot "Redis keys" "1.3_redis"; Close-Windows

Open-Window "Semantic cache" $Root @('python code/hw09_show.py part2')
Start-Sleep 5; Save-Shot "Semantic cache" "2.1_semantic"; Close-Windows

Open-Window "Cache log" $Root @('python code/hw09_show.py log')
Start-Sleep 5; Save-Shot "Cache log" "2.2_cache_log"; Close-Windows

Open-Window "Sweep" $Root @('python code/hw09_show.py sweep')
Start-Sleep 5; Save-Shot "Sweep" "3.1_sweep"; Close-Windows

Open-Window "False hit" $Root @('python code/hw09_show.py falsehit')
Start-Sleep 5; Save-Shot "False hit" "3.2_false_hit"; Close-Windows

Open-Window "Stale test" $Root @('python code/hw09_show.py stale')
Start-Sleep 5; Save-Shot "Stale test" "3.3_stale"; Close-Windows

Open-Window "Revision" $Root @('python code/hw09_show.py revision')
Start-Sleep 5; Save-Shot "Revision" "4.1_revision"; Close-Windows

Open-Window "Lesson reuse" $Root @('python code/hw09_show.py lesson')
Start-Sleep 5; Save-Shot "Lesson reuse" "4.2_lesson"; Close-Windows

Open-Window "Training" $Root @('python code/hw09_show.py training')
Start-Sleep 5; Save-Shot "Training" "4.3_training"; Close-Windows

Open-Window "Validation" $Root @('python code/hw09_show.py validation')
Start-Sleep 5; Save-Shot "Validation" "4.4_validation"; Close-Windows

Open-Window "Test results" $Root @('python code/hw09_show.py test')
Start-Sleep 5; Save-Shot "Test results" "4.5_test"; Close-Windows

Open-Window "Lessons" $Root @('python code/hw09_show.py lessons')
Start-Sleep 5; Save-Shot "Lessons" "4.6_lessons"; Close-Windows

Open-Window "Verify" $Root @('python verify_hw09.py')
Start-Sleep 28; Save-Shot "Verify" "5.1_verify"; Close-Windows

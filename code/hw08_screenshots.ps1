param([ValidateSet("1", "2")][string]$Part = "1")
# HW8 screenshots: opens terminal windows titled with my name, runs the commands and saves each window.
#     powershell -File code\hw08_screenshots.ps1 -Part 1
#     powershell -File code\hw08_screenshots.ps1 -Part 2
$ErrorActionPreference = "Continue"
$Root = "C:\SJSU Assignments\Agentic AI\Assignment_1"
Set-Location $Root
$Name = "Pragya Chourasia"
$Shots = Join-Path $Root "reports\hw08\screenshots"; New-Item -ItemType Directory -Force $Shots | Out-Null
$Tmp = Join-Path $env:TEMP "hw08_windows"; New-Item -ItemType Directory -Force $Tmp | Out-Null
$Kt = "/opt/kafka/bin/kafka-topics.sh"

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Hw8Shot {
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
[void][Hw8Shot]::SetProcessDPIAware()
$Opened = @()

function Open-Window([string]$Label, [string]$Dir, [string[]]$Commands) {
    $file = Join-Path $Tmp ("{0}.ps1" -f ($Label -replace "[^A-Za-z0-9]", "_"))
    $lines = @(
        "`$Host.UI.RawUI.WindowTitle = '$Name - DATA-260 HW8 - $Label'",
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
        $h = [Hw8Shot]::FindByTitle("$Name - DATA-260 HW8 - $Label")
        if ($h -ne [IntPtr]::Zero) { [void][Hw8Shot]::ShowWindow($h, 3); break }
    }
}

function Save-Shot([string]$Label, [string]$Id) {
    $h = [IntPtr]::Zero
    for ($i = 0; $i -lt 20 -and $h -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 500; $h = [Hw8Shot]::FindByTitle("$Name - DATA-260 HW8 - $Label") }
    if ($h -eq [IntPtr]::Zero) { Write-Host "window not found: $Label"; return }
    # minimize then restore, so the window comes to the front even when another window has focus
    [void][Hw8Shot]::ShowWindow($h, 6); Start-Sleep -Milliseconds 400
    [void][Hw8Shot]::ShowWindow($h, 9); [void][Hw8Shot]::ShowWindow($h, 3); [void][Hw8Shot]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 1500
    $r = New-Object Hw8Shot+RECT; [void][Hw8Shot]::DwmGetWindowAttribute($h, 9, [ref]$r, 16)
    $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
    $bmp.Save((Join-Path $Shots "$Id.png"), [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
    Write-Host "saved $Id.png"
}

function Close-Windows { foreach ($p in $script:Opened) { taskkill /PID $p.Id /T /F 2>&1 | Out-Null }; $script:Opened = @() }

if ($Part -eq "1") {
    docker compose up -d --force-recreate listing-worker listing-api 2>&1 | Out-Null
    Start-Sleep 12
    Open-Window "Docker" $Root @(
        'docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"',
        'docker logs --tail 2 s6758_listing_worker',
        'docker logs s6758_listing_api 2>&1 | Select-String "started at|Uvicorn running"'
    )
    Start-Sleep 12; Save-Shot "Docker" "1.1_docker_ps"; Close-Windows

    Open-Window "homework_demo" $Root @('python homework_demo.py')
    Start-Sleep 14; Save-Shot "homework_demo" "1.2_create_get"; Close-Windows

    $demo = Get-Content "$Root\reports\hw08\raw\part1_demo.json" -Raw | ConvertFrom-Json
    $ids = "$($demo.create.correlation_id)|$($demo.get.correlation_id)"
    Open-Window "Worker log" $Root @("docker logs s6758_listing_worker 2>&1 | Select-String '$ids'")
    Start-Sleep 8; Save-Shot "Worker log" "1.3a_worker_log"; Close-Windows
    Open-Window "FastAPI log" $Root @("docker logs s6758_listing_api 2>&1 | Select-String '$ids'")
    Start-Sleep 8; Save-Shot "FastAPI log" "1.3b_api_log"; Close-Windows

    Open-Window "Full sequence" $Root @('python homework_demo.py --sequence')
    Start-Sleep 6; Save-Shot "Full sequence" "1.4_full_sequence"; Close-Windows
}

if ($Part -eq "2") {
    # fresh topics and consumer groups so the journey starts at offset 0
    foreach ($grp in "s6758-planner", "s6758-writer", "s6758-reviewer") {
        docker exec s6758_kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --delete --group $grp 2>&1 | Out-Null
    }
    foreach ($t in "inbox", "tasks", "drafts", "final") {
        docker exec s6758_kafka $Kt --bootstrap-server localhost:9092 --delete --topic "s6758_$t" 2>&1 | Out-Null
    }
    Start-Sleep 5
    Remove-Item "$Root\reports\hw08\raw\part2_journey.jsonl" -ErrorAction SilentlyContinue

    Open-Window "Kafka topics" $Root @(
        "docker exec s6758_kafka $Kt --create --topic s6758_inbox --partitions 1 --replication-factor 1 --bootstrap-server localhost:9092",
        "docker exec s6758_kafka $Kt --create --topic s6758_tasks --partitions 2 --replication-factor 1 --bootstrap-server localhost:9092",
        "docker exec s6758_kafka $Kt --create --topic s6758_drafts --partitions 1 --replication-factor 1 --bootstrap-server localhost:9092",
        "docker exec s6758_kafka $Kt --create --topic s6758_final --partitions 1 --replication-factor 1 --bootstrap-server localhost:9092",
        "docker exec s6758_kafka $Kt --describe --topic s6758_tasks --bootstrap-server localhost:9092"
    )
    Start-Sleep 14; Save-Shot "Kafka topics" "2.1_topics"; Close-Windows

    $Agents = "$Root\kafka_agents"
    Open-Window "Terminal 1 Planner" $Agents @('python planner.py')
    Open-Window "Terminal 2 Writer" $Agents @('python writer.py')
    Open-Window "Terminal 3 Reviewer" $Agents @('python reviewer.py')
    Start-Sleep 10
    Open-Window "Terminal 4 send_question" $Agents @('python send_question.py')
    $log = "$Root\reports\hw08\raw\part2_journey.jsonl"
    for ($i = 0; $i -lt 180; $i++) {
        Start-Sleep 5
        if ((Test-Path $log) -and (Select-String -Path $log -Pattern '"SENDER", "event": "received result' -Quiet)) { break }
    }
    Start-Sleep 3
    Save-Shot "Terminal 1 Planner" "2.2_planner"
    Save-Shot "Terminal 2 Writer" "2.3_writer"
    Save-Shot "Terminal 3 Reviewer" "2.4_reviewer"
    Save-Shot "Terminal 4 send_question" "2.5_final"
    Close-Windows
}

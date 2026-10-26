param([switch]$Auto)  # -Auto: capture both screens automatically into reports\hw07\screenshots
# HW7 Part 1 lint demo: Ruff finds errors -> pre-commit blocks the commit -> fix -> commit succeeds.
# Run from the repository root in its own PowerShell window:
#     powershell -ExecutionPolicy Bypass -File code\hw07_lint_demo.ps1
$ErrorActionPreference = "Continue"
$Name = "Pragya Chourasia"
$Host.UI.RawUI.WindowTitle = "$Name - DATA-260 HW7 - SID 6758"

Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Hw7Shot {
  public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int size);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr p);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  public static IntPtr FindByTitle(string prefix) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, p) => { if (!IsWindowVisible(h)) return true; var sb = new System.Text.StringBuilder(512);
      GetWindowText(h, sb, 512); if (sb.ToString().StartsWith(prefix)) { found = h; return false; } return true; }, IntPtr.Zero);
    return found;
  }
}
"@
[void][Hw7Shot]::SetProcessDPIAware()
function Save-Shot([string]$Id) {
    $dir = Join-Path (Get-Location) "reports\hw07\screenshots"; New-Item -ItemType Directory -Force $dir | Out-Null
    Start-Sleep -Milliseconds 800
    $h = [Hw7Shot]::FindByTitle("$Name - DATA-260 HW7"); [void][Hw7Shot]::ShowWindow($h, 3); [void][Hw7Shot]::SetForegroundWindow($h); Start-Sleep -Milliseconds 900
    $r = New-Object Hw7Shot+RECT; [void][Hw7Shot]::DwmGetWindowAttribute($h, 9, [ref]$r, 16)
    $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
    $bmp.Save((Join-Path $dir "$Id.png"), [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
}
$Py = ".\venv\Scripts\python.exe"
$Files = @(
    "backend/app/auth_jwt.py", "backend/app/main.py", "backend/app/models.py", "backend/app/schema.py",
    "backend/app/crud.py", "backend/app/session_crud.py", "backend/migrate_hw07_users.py",
    "backend/requirements.txt", "pyproject.toml", ".pre-commit-config.yaml", "code/hw07_lint_demo.ps1",
    "code/hw07_fix_lint.py", "reports/hw07/raw/part1_migration_console.txt"
)

function Banner([string]$Title) {
    Write-Host ("=" * 96) -ForegroundColor Cyan
    Write-Host ("  {0}  |  DATA-260 HW7  |  SID4 6758  |  {1}" -f $Name, (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Yellow
    Write-Host ("=" * 96) -ForegroundColor Cyan
}

Clear-Host
Banner "Part 1 - Ruff + pre-commit: lint errors block the commit"
Write-Host "`n> ruff check (Part 1 files)" -ForegroundColor Green
& .\venv\Scripts\ruff.exe check --output-format concise backend/app/main.py backend/app/schema.py backend/app/auth_jwt.py
Write-Host "`n> git add ... ; git commit -m 'HW7 Part 1: JWT auth, roles, Ruff'" -ForegroundColor Green
git add -A -- $Files
git commit -m "HW7 Part 1: JWT auth, roles, Ruff + pre-commit" -- $Files
Write-Host "`n  -> commit exit code $LASTEXITCODE (non-zero = blocked by the pre-commit hook)" -ForegroundColor Magenta
if ($Auto) { Save-Shot "1.6a_lint_blocked" } else { Read-Host "`n  Take screenshot 1 now, then press Enter to fix the issues" }

Clear-Host
Banner "Part 1 - fix the issues, then commit again"
Write-Host "`n> python code\hw07_fix_lint.py" -ForegroundColor Green
& $Py code\hw07_fix_lint.py
Write-Host "`n> ruff check (after fixes)" -ForegroundColor Green
& .\venv\Scripts\ruff.exe check backend/app/main.py backend/app/schema.py backend/app/auth_jwt.py
Write-Host "`n> git add ... ; git commit -m 'HW7 Part 1: JWT auth, roles, Ruff'" -ForegroundColor Green
git add -A -- $Files
git commit -m "HW7 Part 1: JWT auth, roles, Ruff + pre-commit" -- $Files
Write-Host "`n> git log --oneline -1" -ForegroundColor Green
git log --oneline -1
if ($Auto) { Save-Shot "1.6b_lint_fixed_commit"; exit } else { Read-Host "`n  Take screenshot 2 now, then press Enter to close" }

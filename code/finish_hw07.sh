#!/usr/bin/env bash
# HW7: everything after the Part 5 runs, unattended. Log: reports/hw07/raw/_finish_log.txt
cd "/c/SJSU Assignments/Agentic AI/Assignment_1" || exit 1
R=reports/hw07/raw; P="venv/Scripts/python.exe -u"; export PYTHONIOENCODING=utf-8
L=$R/_finish_log.txt
say(){ echo "[$(date -Iseconds)] $*" | tee -a $L; }
run(){ name=$1; shift; { echo "[$(date -Iseconds)] python $*"; $P "$@"; echo "[$(date -Iseconds)] exit $?"; } > $R/$name 2>&1; }

say "waiting for the Part 5 chain"
while [ ! -f $R/_chain_done.txt ]; do sleep 20; done
say "reliability re-run (corrected metric)"
run part2_reliability_console.txt backend/run_hw07_agent.py reliability 21
say "Part 2 / Part 6 screenshots"
powershell -c "Start-Process conhost.exe -ArgumentList 'powershell.exe','-ExecutionPolicy','Bypass','-File','code\take_hw07_screenshots.ps1','-Only','2.A,2.B,2.C,2.E,6.1','-Auto' -WorkingDirectory '$(pwd -W)' -WindowStyle Maximized -Wait"
say "verification"
{ echo "[$(date -Iseconds)] python verify_hw07.py   (commit $(git rev-parse --short HEAD))"; $P verify_hw07.py; echo "[$(date -Iseconds)] exit $?"; } > $R/verify_console.txt 2>&1
say "metrics + run log"
$P backend/make_hw07_metrics.py > /dev/null 2>&1
$P backend/make_hw07_runlog.py >> $L 2>&1
say "report"
S="$TEMP/claude/C--SJSU-Assignments-Agentic-AI-Assignment-1/a7753c08-fdba-41f1-89c6-f315e5d5d2e3/scratchpad/report7"
(cd "$S" && python assemble.py && bash render7.sh final_hw7) >> $L 2>&1
cp "$S/final_hw7.docx" reports/hw07/Chourasia_HW7.docx 2>>$L
cp "$S/final_hw7.pdf" reports/hw07/Chourasia_HW7.pdf 2>>$L && cp "$S/final_hw7.pdf" reports/hw07/Report.pdf
say "done"

# Daily Teacher Web QA run + Slack report. Windows Task Scheduler points here.
# Pass pytest args to change scope, e.g. .\run_daily.ps1 --smoke
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

# Unattended runs go headless: no browser windows appear over whatever the user
# is doing, and the run does not depend on a foreground desktop session.
$env:HEADLESS = "true"

& "$here\.venv\Scripts\python.exe" "$here\run_daily.py" @args
exit $LASTEXITCODE

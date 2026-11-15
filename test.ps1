Push-Location "$PSScriptRoot\backend"
& .\.venv\Scripts\python.exe -m pytest -v
Pop-Location

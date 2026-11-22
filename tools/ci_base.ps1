# Instala a última versão publicada, copia a pasta instalada para "base-anterior" (base da atualização
# pequena) e desinstala. Grava BASE_VERSAO no ambiente do GitHub Actions.
$ErrorActionPreference = "Stop"
try {
  $info = Invoke-RestMethod "https://github.com/lohanlilson/Instantia/releases/latest/download/versao.json"
} catch { Write-Host "Sem versão anterior publicada."; exit 0 }
$v = $info.versao
Invoke-WebRequest $info.instalador.url -OutFile anterior.exe
$p = Start-Process .\anterior.exe -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -PassThru; $p.WaitForExit()
Start-Sleep 5; Get-Process Instantia -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep 2
$key = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{8CFC6425-FE9E-43F3-B780-04DB19E19F23}_is1"
$dir = (Get-ItemProperty $key).InstallLocation
Copy-Item $dir "base-anterior" -Recurse
$p = Start-Process (Join-Path $dir "unins000.exe") -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES' -PassThru; $p.WaitForExit()
Start-Sleep 3
"BASE_VERSAO=$v" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
Write-Host "Base para a atualização pequena: versão $v"

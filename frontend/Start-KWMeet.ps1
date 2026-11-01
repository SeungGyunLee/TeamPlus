param([ValidateSet('start','emulator','android','check','bundle','apk')][string]$Task = 'start', [switch]$ColdBoot)
$ErrorActionPreference = 'Stop'
$projectRoot = (Get-Item -LiteralPath $PSScriptRoot).Target
if (!$projectRoot) { $projectRoot = $PSScriptRoot }
Set-Location -LiteralPath $projectRoot
foreach ($name in @('ANDROID_HOME','ANDROID_SDK_ROOT','ANDROID_AVD_HOME','ANDROID_USER_HOME','JAVA_HOME','GRADLE_USER_HOME')) {
  $configured = [Environment]::GetEnvironmentVariable($name,'User')
  if ($configured) { [Environment]::SetEnvironmentVariable($name,$configured,'Process') }
}
if (!$env:ANDROID_HOME) {
  $defaultSdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
  if (Test-Path -LiteralPath $defaultSdk) { $env:ANDROID_HOME = $defaultSdk }
}
if ($env:ANDROID_HOME) {
  $env:PATH = "$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\emulator;$env:PATH"
  $androidTemp = Join-Path (Split-Path -Parent $env:ANDROID_HOME) 'Temp'
  if (Test-Path -LiteralPath $androidTemp) { $env:TEMP=$androidTemp; $env:TMP=$androidTemp }
}
if ($env:JAVA_HOME) { $env:PATH = "$env:JAVA_HOME\bin;$env:PATH" }
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$runtimeRoot = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
if ($nodeCommand) { $nodeExe = $nodeCommand.Source }
elseif (Test-Path -LiteralPath (Join-Path $runtimeRoot 'bin/node.exe')) { $nodeExe = Join-Path $runtimeRoot 'bin/node.exe' }
else { throw 'Node.js LTS를 설치한 후 터미널을 다시 열어 주세요: https://nodejs.org/' }
$env:PATH = "$(Split-Path -Parent $nodeExe);$env:PATH"
# Windows can resolve localhost to IPv6 only; adb reverse forwards IPv4.
$env:NODE_OPTIONS = (($env:NODE_OPTIONS + ' --dns-result-order=ipv4first').Trim())
$pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
$runtimePnpm = Join-Path $runtimeRoot 'node_modules/pnpm/bin/pnpm.cjs'
$pinnedPnpm = if ($env:ANDROID_HOME) { Join-Path (Split-Path -Parent $env:ANDROID_HOME) 'Tools\pnpm10\bin\pnpm.cjs' } else { '' }
function Install-Project {
  if ($pinnedPnpm -and (Test-Path -LiteralPath $pinnedPnpm)) { & $nodeExe $pinnedPnpm install --frozen-lockfile --store-dir (Join-Path (Split-Path -Parent $env:ANDROID_HOME) 'Cache\pnpm10cache') }
  elseif ($pnpmCommand) { & $pnpmCommand.Source install --frozen-lockfile }
  elseif (Test-Path -LiteralPath $runtimePnpm) { & $nodeExe $runtimePnpm install --frozen-lockfile }
  else { throw 'pnpm 10을 먼저 설치해 주세요: npm install --global pnpm@10.28.2' }
  if ($LASTEXITCODE -ne 0) { throw '의존성 설치에 실패했습니다.' }
}
function Run-Node([string]$File, [string[]]$Arguments) {
  & $nodeExe $File @Arguments
  if ($LASTEXITCODE -ne 0) { throw "실행에 실패했습니다: $File" }
}
if (!(Test-Path -LiteralPath 'node_modules/expo/bin/cli')) { Install-Project }
switch ($Task) {
  'start' { Run-Node 'node_modules/expo/bin/cli' @('start','--lan') }
  'emulator' {
    if (!$env:ANDROID_HOME) { throw 'Android SDK가 설치되어 있지 않습니다.' }
    $adbExe = Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'
    $emulatorExe = Join-Path $env:ANDROID_HOME 'emulator\emulator.exe'
    if (!(Test-Path -LiteralPath $adbExe) -or !(Test-Path -LiteralPath $emulatorExe)) { throw 'Android SDK의 platform-tools와 emulator를 설치해 주세요.' }
    $devices = & $adbExe devices
    $virtualDevice = $devices | Where-Object { $_ -match '^emulator-\d+\s+device$' } | Select-Object -First 1
    if (!$virtualDevice) {
      $avds = & $emulatorExe -list-avds
      $avdName = if ($avds -contains 'KW_Meet_API_36') { 'KW_Meet_API_36' } else { $avds | Select-Object -First 1 }
      if (!$avdName) { throw '가상폰이 없습니다. Android Studio에서 가상 기기를 생성해 주세요.' }
      $emulatorArguments = @('-avd',$avdName,'-no-boot-anim','-gpu','host','-feature','-Vulkan','-lowram')
      if ($ColdBoot) { $emulatorArguments += '-no-snapshot-load' }
      Start-Process -WindowStyle Hidden -FilePath $emulatorExe -ArgumentList $emulatorArguments -WorkingDirectory (Split-Path -Parent $emulatorExe) -RedirectStandardOutput (Join-Path $env:TEMP 'kwmeet-emulator.log') -RedirectStandardError (Join-Path $env:TEMP 'kwmeet-emulator-error.log') | Out-Null
    }
    Write-Output '가상폰이 켜질 때까지 기다리는 중입니다...'
    $bootDeadline = (Get-Date).AddMinutes(4)
    $booted = $false
    while ((Get-Date) -lt $bootDeadline) {
      $deviceLine = & $adbExe devices | Where-Object { $_ -match '^emulator-\d+\s+device$' } | Select-Object -First 1
      if ($deviceLine) {
        $serial = ($deviceLine -split '\s+')[0]
        if ((& $adbExe -s $serial shell getprop sys.boot_completed 2>$null) -match '1') { $booted=$true; break }
      }
      Start-Sleep -Seconds 2
    }
    if (!$booted) { throw '가상폰 부팅을 확인하지 못했습니다. 가속 드라이버와 가상폰 오류를 확인해 주세요.' }
    Run-Node 'node_modules/expo/bin/cli' @('start','--android','--localhost','--max-workers','1')
  }
  'android' { Run-Node 'node_modules/expo/bin/cli' @('run:android') }
  'bundle' { Run-Node 'node_modules/expo/bin/cli' @('export','--platform','android','--output-dir','dist/android') }
  'check' {
    Run-Node 'node_modules/typescript/bin/tsc' @('--noEmit')
    $testFiles = @(Get-ChildItem -LiteralPath 'tests' -Filter '*.test.ts' | ForEach-Object FullName)
    Run-Node 'node_modules/tsx/dist/cli.mjs' (@('--test') + $testFiles)
    Run-Node 'node_modules/expo/bin/cli' @('install','--check')
  }
  'apk' {
    if (!(Get-Command java -ErrorAction SilentlyContinue)) { throw 'JDK 17을 설치하고 JAVA_HOME 및 PATH를 설정해 주세요.' }
    if (!$env:ANDROID_HOME) { throw 'Android Studio SDK 설치 후 ANDROID_HOME을 설정해 주세요.' }
    Run-Node 'node_modules/expo/bin/cli' @('prebuild','--platform','android','--no-install')
    Push-Location -LiteralPath 'android'
    try { & .\gradlew.bat assembleDebug; if ($LASTEXITCODE -ne 0) { throw 'Gradle 빌드 실패' } }
    finally { Pop-Location }
    New-Item -ItemType Directory -Path 'builds' -Force | Out-Null
    Copy-Item -LiteralPath 'android/app/build/outputs/apk/debug/app-debug.apk' -Destination 'builds/KW-Meet-debug.apk' -Force
    Write-Output 'APK: builds/KW-Meet-debug.apk (Metro 개발 서버가 필요합니다.)'
  }
}

# ==============================================================================
# Orbital Pulse — Windows Automated Setup & Bootstrapping Script
# ==============================================================================
# This script verifies and installs all prerequisite runtimes, CLI tools,
# Node dependencies, and Python virtual environments needed to develop and
# run Orbital Pulse on Windows.
#
# Requirements handled:
#   - Git (Git.Git via winget)
#   - Node.js LTS (OpenJS.NodeJS.LTS via winget)
#   - pnpm (pnpm.pnpm via winget or npm)
#   - Python 3.10 (Python.Python.3.10 via winget)
#   - Project .env configuration
#   - Frontend npm/pnpm package installation
#   - SatQuery AI Python virtual environment & pip requirements
# ==============================================================================

[CmdletBinding()]
param(
    [switch]$SkipSystemPackages,   # Skip winget checks and only install project packages
    [switch]$SetupML,              # Also clone GeoChat submodule & configure ML environment
    [switch]$NonInteractive        # Run without pausing for user input at the end
)

$ErrorActionPreference = "Continue"

# Helper for formatted console messages
function Write-Step([string]$stepNumber, [string]$title) {
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host " [$stepNumber] $title" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
}

function Write-Success([string]$message) {
    Write-Host "  [+] $message" -ForegroundColor Green
}

function Write-Info([string]$message) {
    Write-Host "  [*] $message" -ForegroundColor Gray
}

function Write-WarningMsg([string]$message) {
    Write-Host "  [!] $message" -ForegroundColor Yellow
}

function Write-Fail([string]$message) {
    Write-Host "  [-] $message" -ForegroundColor Red
}

# Function to refresh environment PATH in the current PowerShell process
function Refresh-EnvPath {
    Write-Info "Refreshing session PATH environment variable..."
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

# Function to test command existence
function Test-CommandAvailable([string]$commandName) {
    $cmd = Get-Command $commandName -ErrorAction SilentlyContinue
    return ($null -ne $cmd)
}

# Function to resolve the best available Python command
function Get-AvailablePython {
    # 1. Prefer Python 3.10 in py launcher if available
    if (Test-CommandAvailable "py") {
        $pyList = py -0 2>$null
        if ($pyList -match "3\.10") {
            return "py -3.10"
        }
    }
    # 2. Check standard python command
    if (Test-CommandAvailable "python") {
        return "python"
    }
    # 3. Fallback to py default
    if (Test-CommandAvailable "py") {
        return "py"
    }
    return $null
}

# Function to install a package using winget with explicit --source winget
function Install-WingetPackage([string]$packageId, [string]$friendlyName) {
    Write-Info "Installing $friendlyName ($packageId) via winget..."
    try {
        & winget install --id $packageId -e --source winget --accept-source-agreements --accept-package-agreements --silent
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 3010) {
            Write-Success "$friendlyName installed successfully."
            Refresh-EnvPath
            return $true
        } else {
            Write-WarningMsg "winget exited with code $LASTEXITCODE while installing $friendlyName."
            Refresh-EnvPath
            return $false
        }
    } catch {
        Write-Fail "Failed to install $friendlyName via winget: $_"
        return $false
    }
}

# ------------------------------------------------------------------------------
# Script Header
# ------------------------------------------------------------------------------
Clear-Host
Write-Host "==================================================================" -ForegroundColor Magenta
Write-Host "          Orbital Pulse - Windows Environment Bootstrapper        " -ForegroundColor Magenta
Write-Host "==================================================================" -ForegroundColor Magenta
Write-Host "Project Root: $PSScriptRoot" -ForegroundColor Gray
Write-Host ""

# Ensure we are executing in the project root directory
Set-Location $PSScriptRoot

# ------------------------------------------------------------------------------
# STEP 1: Check Winget Availability
# ------------------------------------------------------------------------------
Write-Step "1/6" "Checking Windows Package Manager (winget)"

if (-not $SkipSystemPackages) {
    if (Test-CommandAvailable "winget") {
        $wingetVer = & winget --version
        Write-Success "winget is available (version $wingetVer)"
    } else {
        Write-Fail "winget is not available on this system."
        Write-WarningMsg "Please install 'App Installer' from the Microsoft Store or download winget from:"
        Write-WarningMsg "https://github.com/microsoft/winget-cli/releases"
        Write-WarningMsg "Proceeding with existing installed tools only..."
    }
} else {
    Write-Info "Skipping system package installation (-SkipSystemPackages flag passed)."
}

# ------------------------------------------------------------------------------
# STEP 2: Verify & Install Core System Prerequisites
# ------------------------------------------------------------------------------
Write-Step "2/6" "Verifying Developer Toolchain (Git, Node.js, pnpm, Python)"

if (-not $SkipSystemPackages -and (Test-CommandAvailable "winget")) {
    # --- 1. Git ---
    if (Test-CommandAvailable "git") {
        $gitVer = & git --version
        Write-Success "Git already installed: $gitVer"
    } else {
        Install-WingetPackage "Git.Git" "Git Version Control"
    }

    # --- 2. Node.js (LTS >= 20) ---
    $needNode = $true
    if (Test-CommandAvailable "node") {
        $nodeVer = & node --version
        Write-Info "Found Node.js: $nodeVer"
        # Extract major version number (e.g. v20.x -> 20)
        if ($nodeVer -match "^v?(\d+)") {
            $major = [int]$matches[1]
            if ($major -ge 20) {
                Write-Success "Node.js version is compatible (>= 20)."
                $needNode = $false
            } else {
                Write-WarningMsg "Current Node.js version ($nodeVer) is older than v20."
            }
        }
    }
    if ($needNode) {
        Install-WingetPackage "OpenJS.NodeJS.LTS" "Node.js LTS"
    }

    # --- 3. pnpm ---
    if (Test-CommandAvailable "pnpm") {
        $pnpmVer = & pnpm --version
        Write-Success "pnpm already installed: v$pnpmVer"
    } else {
        Write-Info "pnpm not found. Attempting install via winget..."
        $installed = Install-WingetPackage "pnpm.pnpm" "pnpm Package Manager"
        if (-not $installed -and (Test-CommandAvailable "npm")) {
            Write-Info "Falling back to 'npm install -g pnpm'..."
            & npm install -g pnpm
            Refresh-EnvPath
        }
    }

    # --- 4. Python 3.10 ---
    $hasPython310 = $false
    if (Test-CommandAvailable "py") {
        $pyList = py -0 2>$null
        if ($pyList -match "3\.10") {
            Write-Success "Python 3.10 is registered in Windows py launcher."
            $hasPython310 = $true
        }
    }
    if (-not $hasPython310 -and (Test-CommandAvailable "python")) {
        $pyVer = & python --version 2>$null
        if ($pyVer -match "3\.10") {
            Write-Success "Python 3.10 detected: $pyVer"
            $hasPython310 = $true
        }
    }
    if (-not $hasPython310) {
        Write-Info "Python 3.10 not found. Installing via winget..."
        Install-WingetPackage "Python.Python.3.10" "Python 3.10 Runtime"
    }
} else {
    Write-Info "Tool verification completed (skipping automatic installations)."
}

Refresh-EnvPath

# ------------------------------------------------------------------------------
# STEP 3: Environment Configuration (.env)
# ------------------------------------------------------------------------------
Write-Step "3/6" "Checking Project Environment Configuration"

$envFile = Join-Path $PSScriptRoot ".env"
$envExample = Join-Path $PSScriptRoot ".env.example"

if (Test-Path $envFile) {
    Write-Success ".env configuration file is present."
} else {
    if (Test-Path $envExample) {
        Write-Info "Creating .env from .env.example..."
        Copy-Item -Path $envExample -Destination $envFile
        Write-Success ".env created."
        Write-WarningMsg "NOTE: Set your 'VITE_CESIUM_ION_TOKEN' in .env if you plan to use Cesium Ion asset terrain."
    } else {
        Write-WarningMsg ".env.example was not found. Please create .env manually."
    }
}

# ------------------------------------------------------------------------------
# STEP 4: Install Node.js Dependencies (Frontend & Express Orbit Proxy)
# ------------------------------------------------------------------------------
Write-Step "4/6" "Installing Frontend & Server Node Dependencies"

# Choose package manager: prefer pnpm, fallback to npx pnpm or npm
$pkgManager = $null
if (Test-CommandAvailable "pnpm") {
    $pkgManager = "pnpm"
} elseif (Test-CommandAvailable "npx") {
    $pkgManager = "npx pnpm"
} elseif (Test-CommandAvailable "npm") {
    $pkgManager = "npm"
}

if ($pkgManager) {
    Write-Info "Executing: $pkgManager install..."
    try {
        if ($pkgManager -eq "npx pnpm") {
            & npx pnpm install
        } elseif ($pkgManager -eq "pnpm") {
            & pnpm install
        } else {
            & npm install
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Node dependencies installed successfully."
        } else {
            Write-Fail "Package manager exited with code $LASTEXITCODE."
        }
    } catch {
        Write-Fail "Failed to install Node dependencies: $_"
    }
} else {
    Write-Fail "Neither pnpm nor npm was found in the current session PATH. Please restart PowerShell and re-run."
}

# ------------------------------------------------------------------------------
# STEP 5: SatQuery AI Python Service Setup (Virtual Environment)
# ------------------------------------------------------------------------------
Write-Step "5/6" "Setting Up SatQuery AI Python Virtual Environment"

$satqueryDir = Join-Path $PSScriptRoot "satquery-service"
$reqFile = Join-Path $satqueryDir "requirements.txt"
$venvDir = Join-Path $satqueryDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

# Resolve best python command for creating venv
$systemPython = Get-AvailablePython

if ($systemPython) {
    # 1. Create venv if missing
    if (-not (Test-Path $venvPython)) {
        Write-Info "Creating virtual environment at '$venvDir' using $systemPython..."
        if ($systemPython -eq "py -3.10") {
            py -3.10 -m venv $venvDir
        } elseif ($systemPython -eq "py") {
            py -m venv $venvDir
        } else {
            & $systemPython -m venv $venvDir
        }
    }

    if (Test-Path $venvPython) {
        Write-Success "Virtual environment is ready at $venvDir"

        # 2. Upgrade pip & build tools
        Write-Info "Upgrading pip, setuptools, and wheel in virtual environment..."
        & $venvPython -m pip install --upgrade pip setuptools wheel --quiet

        # 3. Install requirements
        if (Test-Path $reqFile) {
            Write-Info "Installing satquery-service dependencies from requirements.txt..."
            & $venvPython -m pip install -r $reqFile
            if ($LASTEXITCODE -eq 0) {
                Write-Success "SatQuery AI dependencies installed successfully."
            } else {
                Write-WarningMsg "Pip encountered warnings or errors installing requirements."
            }
        } else {
            Write-WarningMsg "requirements.txt not found at $reqFile"
        }
    } else {
        Write-Fail "Failed to create Python virtual environment."
    }
} else {
    Write-WarningMsg "No Python executable found. Please install Python 3.10+ and re-run this script."
}

# ------------------------------------------------------------------------------
# OPTIONAL: GeoChat-7B Model Repository Setup
# ------------------------------------------------------------------------------
if ($SetupML) {
    Write-Step "ML" "Setting Up GeoChat-7B Local Submodule"
    $mlDir = Join-Path $PSScriptRoot "ml\geochat"
    $geochatRepo = Join-Path $mlDir "GeoChat"

    if (-not (Test-Path $geochatRepo)) {
        Write-Info "Cloning official GeoChat repository into '$geochatRepo'..."
        & git clone https://github.com/mbzuai-oryx/GeoChat.git $geochatRepo
        if ($LASTEXITCODE -eq 0) {
            Push-Location $geochatRepo
            Write-Info "Checking out pinned working commit 4850920e005a849bd224d0ce35aa9db031fa5155..."
            & git checkout 4850920e005a849bd224d0ce35aa9db031fa5155
            Pop-Location
            Write-Success "GeoChat repository cloned and pinned successfully."
        }
    } else {
        Write-Success "GeoChat repository already exists at $geochatRepo."
    }
}

# ------------------------------------------------------------------------------
# STEP 6: Run Self-Tests / Verification
# ------------------------------------------------------------------------------
Write-Step "6/6" "Verification & Health Check"

$typecheckOk = $false
$testsOk = $false

if (Test-CommandAvailable "pnpm") {
    Write-Info "Running TypeScript typecheck..."
    & pnpm typecheck
    if ($LASTEXITCODE -eq 0) { $typecheckOk = $true; Write-Success "TypeScript typecheck: PASSED (0 errors)" }

    Write-Info "Running unit tests..."
    & pnpm test
    if ($LASTEXITCODE -eq 0) { $testsOk = $true; Write-Success "Unit tests: PASSED" }
} elseif (Test-CommandAvailable "npm") {
    Write-Info "Running TypeScript typecheck..."
    & npm run typecheck
    if ($LASTEXITCODE -eq 0) { $typecheckOk = $true; Write-Success "TypeScript typecheck: PASSED (0 errors)" }

    Write-Info "Running unit tests..."
    & npm test
    if ($LASTEXITCODE -eq 0) { $testsOk = $true; Write-Success "Unit tests: PASSED" }
}

# ------------------------------------------------------------------------------
# Summary & Developer Instructions
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "              Orbital Pulse Setup Complete!                       " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "How to start the development servers:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Start Frontend & Express Orbit Proxy (Port 8080):" -ForegroundColor White
Write-Host "     pnpm dev" -ForegroundColor Yellow
Write-Host "     (or: npm run dev)" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Start SatQuery AI Backend Service (Port 8082):" -ForegroundColor White
Write-Host "     cd satquery-service" -ForegroundColor Yellow
Write-Host "     .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "     uvicorn main:app --host 0.0.0.0 --port 8082 --reload" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Open Application in your Browser:" -ForegroundColor White
Write-Host "     http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "Optional Full ML Setup:" -ForegroundColor Gray
Write-Host "  To configure local GPU GeoChat-7B 4-bit execution, run:" -ForegroundColor Gray
Write-Host "  .\setup.ps1 -SetupML" -ForegroundColor Gray
Write-Host ""

if (-not $NonInteractive) {
    Write-Host "Press any key to close this window..." -ForegroundColor Gray
    [void][System.Console]::ReadKey($true)
}

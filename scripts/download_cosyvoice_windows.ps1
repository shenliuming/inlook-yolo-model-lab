<#
.SYNOPSIS
    Downloads the CosyVoice2-0.5B model to a specified directory on Windows.
.DESCRIPTION
    This script automates the download of the CosyVoice2-0.5B model, which is
    required for the INLOOK Studio TTS feature. It supports downloading from
    either ModelScope or HuggingFace.
.PARAMETER ModelDir
    The target directory to download the model into. Defaults to D:\Models\CosyVoice2-0.5B
.PARAMETER Source
    The source to download from. Valid options are "modelscope" or "huggingface". Defaults to "modelscope".
#>

param (
    [string]$ModelDir = "D:\Models\CosyVoice2-0.5B",
    [ValidateSet("modelscope", "huggingface")]
    [string]$Source = "modelscope"
)

Write-Host "=== INLOOK CosyVoice Model Downloader (Windows) ==="

# Check Python
$pythonExists = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pythonExists) {
    Write-Error "Python is not installed or not in PATH. Please install Python first."
    exit 1
}

Write-Host "Target Directory: $ModelDir"
Write-Host "Source: $Source"

if (-not (Test-Path -Path $ModelDir)) {
    Write-Host "Creating directory: $ModelDir"
    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
}

Write-Host "Installing required Python packages..."
python -m pip install huggingface_hub modelscope --quiet

Write-Host "Starting download... This may take a while depending on your network."

if ($Source -eq "modelscope") {
    $script = @"
from modelscope import snapshot_download
import os

model_dir = snapshot_download('iic/CosyVoice2-0.5B', local_dir=r'$ModelDir')
print(f'Model downloaded successfully to: {model_dir}')
"@
    python -c $script
} else {
    $script = @"
from huggingface_hub import snapshot_download
import os

model_dir = snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir=r'$ModelDir')
print(f'Model downloaded successfully to: {model_dir}')
"@
    python -c $script
}

Write-Host "`nDownload Complete. Contents of $ModelDir:"
Get-ChildItem -Path $ModelDir | Select-Object Name, Length
Write-Host "`nReminder: Set COSYVOICE_MODEL_DIR=$ModelDir in your .env.local file."

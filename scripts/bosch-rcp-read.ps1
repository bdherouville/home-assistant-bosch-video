param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$CameraHost,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(0x)?[0-9a-fA-F]+$')]
    [string]$Command,

    [ValidateSet('F_FLAG', 'T_OCTET', 'T_WORD', 'T_DWORD', 'P_STRING', 'P_OCTET')]
    [string]$Type = 'P_OCTET',

    [ValidateRange(0, 255)]
    [int]$Num = 1,

    [string]$EnvFile = (Join-Path $PSScriptRoot '..\env.txt'),

    [string]$UsernameKey = 'BOSCH_CAMERA_USERNAME',

    [string]$PasswordKey = 'BOSCH_CAMERA_PASSWORD'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Credential file not found: $EnvFile"
}

$settings = @{}
Get-Content -LiteralPath $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
        $settings[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
    }
}

foreach ($requiredKey in $UsernameKey, $PasswordKey) {
    if ([string]::IsNullOrWhiteSpace($settings[$requiredKey])) {
        throw "Missing $requiredKey in $EnvFile"
    }
}

$normalizedCommand = if ($Command.StartsWith('0x')) {
    $Command.ToLowerInvariant()
} else {
    "0x$($Command.ToLowerInvariant())"
}

$queryParts = @(
    "command=$([uri]::EscapeDataString($normalizedCommand))"
    "type=$([uri]::EscapeDataString($Type))"
    'direction=READ'
    "num=$Num"
)
$uri = "http://$CameraHost/rcp.xml?$($queryParts -join '&')"
$credentials = "$($settings[$UsernameKey]):$($settings[$PasswordKey])"

$response = & curl.exe `
    --silent `
    --show-error `
    --max-time 10 `
    --digest `
    --user $credentials `
    --write-out "`nHTTP_STATUS:%{http_code}" `
    $uri

if ($LASTEXITCODE -ne 0) {
    throw "The camera request failed (curl exit code $LASTEXITCODE)."
}

$responseText = $response -join "`n"
$statusMatch = [regex]::Match($responseText, 'HTTP_STATUS:(\d+)\s*$')
if (-not $statusMatch.Success) {
    throw 'The camera response did not contain an HTTP status.'
}

$httpStatus = [int]$statusMatch.Groups[1].Value
$xmlText = $responseText -replace '\s*HTTP_STATUS:\d+\s*$', ''

if ($httpStatus -ne 200) {
    throw "The camera returned HTTP $httpStatus."
}

try {
    [xml]$document = $xmlText
} catch {
    throw "The camera response was not valid XML: $($_.Exception.Message)"
}

$resultNode = $document.rcp.result
$errorNode = $resultNode.err

[pscustomobject]@{
    camera_host = $CameraHost
    command   = $normalizedCommand
    type      = $Type
    num       = $Num
    auth      = [int]$document.rcp.auth
    protocol  = [string]$document.rcp.protocol
    error     = if ($null -ne $errorNode) { [string]$errorNode } else { $null }
    result    = if ($null -eq $errorNode) {
        ($resultNode.InnerText -replace '\s+', ' ').Trim()
    } else {
        $null
    }
}

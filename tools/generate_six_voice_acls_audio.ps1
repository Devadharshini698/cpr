param(
    [string]$SourceScript = "C:\Users\devad\.codex\attachments\362a4724-d894-4bf0-92eb-4ec12f742c18\Pasted text.txt",
    [string]$OutputWav = "C:\Users\devad\Documents\Codex\2026-09-23\https-github-com-devadharshini698-cpr-debriefing\work\final_imsr\backend\debriefing\samples\six_voice_acls_role_test.wav"
)

# Produces a role-labelled training fixture.  It is synthetic demonstration
# audio only and must not be represented as an observed clinical recording.
Add-Type -AssemblyName System.Speech

$profiles = @{
    Arun    = @{ Voice = "Microsoft Ravi";         Rate = -1; Intro = "Hello, I am Arun, the team leader for this resuscitation." }
    Priya   = @{ Voice = "Microsoft Heera";        Rate = -1; Intro = "Hello, I am Priya. I am responsible for chest compressions." }
    Rahul   = @{ Voice = "Microsoft David";        Rate = 0;  Intro = "Hello, I am Rahul. I am responsible for airway and breathing." }
    Divya   = @{ Voice = "Microsoft Zira";         Rate = 0;  Intro = "Hello, I am Divya. I operate the defibrillator and ECG monitor." }
    Karthik = @{ Voice = "Microsoft Mark";         Rate = -1; Intro = "Hello, I am Karthik. I establish IV access and administer medication." }
    Meena   = @{ Voice = "Microsoft Zira Desktop"; Rate = -2; Intro = "Hello, I am Meena. I am the timekeeper and recorder." }
}

if (-not (Test-Path -LiteralPath $SourceScript)) {
    throw "The supplied role script was not found: $SourceScript"
}

$outputDirectory = Split-Path -Parent $OutputWav
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Remove-Item -LiteralPath $OutputWav -Force -ErrorAction SilentlyContinue

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Volume = 100
$synth.SetOutputToWaveFile($OutputWav)

function Speak-RoleLine([string]$Role, [string]$Text, [int]$PauseMilliseconds = 1800) {
    $profile = $profiles[$Role]
    $synth.SelectVoice($profile.Voice)
    $synth.Rate = $profile.Rate
    $escaped = [System.Security.SecurityElement]::Escape($Text.Trim())
    # The pauses model normal team turn-taking. Speech itself remains near a
    # natural conversational pace, rather than being artificially slowed.
    $synth.SpeakSsml("<speak version='1.0' xml:lang='en-US'><prosody rate='0%'>$escaped</prosody><break time='$PauseMilliseconds`ms'/></speak>")
}

try {
    foreach ($role in @("Arun", "Priya", "Rahul", "Divya", "Karthik", "Meena")) {
        Speak-RoleLine $role $profiles[$role].Intro 1200
    }

    foreach ($line in Get-Content -LiteralPath $SourceScript) {
        if ($line -match '^(Arun|Priya|Rahul|Divya|Karthik|Meena):\s*[“\"]?(.*?)[”\"]?\s*$') {
            Speak-RoleLine $matches[1] $matches[2]
        }
    }
}
catch {
    $_ | Out-File -LiteralPath "$OutputWav.error.txt" -Encoding utf8
    throw
}
finally {
    $synth.Dispose()
}

Write-Output "Created: $OutputWav"

# INLOOK Studio Gemini Working Rules

You are assisting with the INLOOK Studio / inlook-yolo-model-lab repository.

## Product positioning

INLOOK Studio is an AI content creation workbench for creators working with their own or authorized scripts, audio, and video materials.

Safe external wording:

* owned materials
* authorized materials
* local video files
* manual scripts
* script organization
* content review
* AI rewriting
* voice generation
* creator workflow

Do not describe the product as:

* crawling Douyin / Bilibili / TikTok
* scraping videos
* downloading other people’s videos
* extracting unauthorized platform content

## Current engineering principle

Do not do vibe coding.

Always follow:

1. Audit first.
2. Make one change at a time.
3. Do not modify unrelated modules.
4. Do not add new features unless explicitly requested.
5. Do not mock success.
6. Do not fallback to deprecated logic.
7. Do not show raw JSON responses to users.
8. Do not do unrelated UI beautification.
9. After every change, run validation.
10. If validation fails, stop and report.

## Current main workflow

The minimum workflow is:

manual script / video transcript
→ DeepSeek rewrite
→ user clicks “Use this version”
→ write into currentProject.currentScript
→ choose voice
→ CosyVoice generates currentAudio
→ preview audio
→ later digital human / subtitles / BGM / export

## currentProject is the source of truth

The frontend should converge toward:

currentProject = {
projectId: null,

material: null,
materialMode: "empty",

originalText: "",
originalTextSource: "empty",

rewriteVersions: [],
selectedRewriteVersionId: null,

currentScript: "",
currentScriptSource: "",
currentScriptTitle: "",

selectedVoiceId: "",
selectedVoiceType: "",
currentAudio: null,

selectedAvatarId: "",
digitalHumanVideo: null,

subtitles: null,
bgm: null,
exportResult: null
}

Rules:

* Column 1 only manages originalText.
* Column 2 rewrites originalText into currentScript.
* Column 3 only uses currentScript + selectedVoiceId to generate currentAudio.
* Column 4 reads currentScript/currentAudio for subtitles/BGM/export.
* Column 5 only displays currentProject state.

## TTS rules

TTS generation must only read:

currentProject.currentScript

Never use:

* originalText
* material.description
* material.title
* selected DOM text
* old script state
* platform description
* reference.wav transcription
* previous task cache

If currentProject.currentScript is empty, disable TTS generation.

CosyVoice is the main TTS engine.

Do not fallback to MOSS.
Do not mock success.
Do not return reference.wav as generated output.

## Voice profile rules

Voice profiles must come from:

GET /api/v1/voices

Do not hardcode old MOSS voices.
Do not append local duplicate voices.
After creating a voice, reload GET /api/v1/voices.
Deduplicate by voiceId.

A voice profile is valid only if:

* reference.wav exists
* reference.wav is usable
* promptText exists
* promptText matches the reference audio
* status is ready

Invalid voice profiles must not silently pass TTS generation.

## Copy rewrite rules

/api/v1/copy/rewrite must normalize output to:

{
"code": 0,
"message": "success",
"data": {
"versions": [
{
"id": "A",
"title": "...",
"text": "...",
"reason": "..."
}
]
}
}

Frontend must only read:

data.versions[].text

Do not display raw model JSON.
Do not display “model returned”.
Do not expose raw API responses to users.

## Digital human status

Do not implement HeyGem / Duix / LongCat locally on this Mac.

Current decision:

* Local Easy-Wav2Lip POC can be tested outside the main repo.
* Do not integrate Wav2Lip into INLOOK main workflow yet.
* Future digital human should be provider based.

Future concept:

currentScript + currentAudio + selectedAvatarId
→ digitalHumanProvider
→ talking.mp4

## Validation commands

When modifying backend:

python3 -m compileall app

When modifying frontend:

npm run build

Always report:

1. Files modified.
2. Why each file changed.
3. Validation result.
4. What was not modified.
5. Remaining risks.

## Forbidden actions

Do not:

* put model files into git
* put large datasets into git
* edit unrelated modules
* delete runtime data without confirmation
* change deployment configs without confirmation
* expose API keys
* expose SSH keys
* expose private user media
* use fake success responses
* hide errors behind vague messages
* make broad refactors without explicit approval

## Preferred workflow

For every task:

1. Restate the task.
2. Inspect relevant files.
3. Explain the minimal plan.
4. Ask before risky operations.
5. Make the smallest change.
6. Run validation.
7. Output a concise report.

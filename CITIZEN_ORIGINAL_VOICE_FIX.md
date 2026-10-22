# Citizen Listen Back — Original Voice Fix

- `frontend/js/complaint.js`: Listen Back now plays the original microphone recording using `MediaRecorder` and an in-browser audio object URL. It no longer calls browser TTS, `/voice/speak`, or external services for this button.
- Keeps existing browser speech-to-text transcription to fill the complaint description.
- Audio is **temporary only in the citizen browser**, is replaced on re-recording, and is freed on page exit. Audio is **not** added to the complaint submission or exposed through department portals.
- Requires microphone permission and a secure browser context (localhost or HTTPS). Recognition availability is still browser/language-dependent, but playback of a recorded voice is language-independent.
- The shared TTS utility and backend speech endpoint are left in place for compatibility; citizen Listen Back no longer invokes them.
- A recording may be replayable even if speech recognition fails to transcribe it. Users can edit the transcript before submitting.

## Checks
JavaScript syntax check and archive validation performed. Live microphone playback must be tested in a browser on your device.

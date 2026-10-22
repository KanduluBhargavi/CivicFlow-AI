# CivicFlow voice complaint long recording fix

- Voice recognition can end after a short silence even when `continuous=true`.
- The citizen's `MediaRecorder` now stays active until **Stop Listening** is clicked, independent of recognition pauses.
- Speech recognition restarts after unexpected silence, preserving finalized transcript chunks across restarts and not double-counting repeated recognition results.
- Transcription is appended to the description once, only when the recording is stopped.
- Permanent microphone/language/network recognition errors stop transcription with a clear message; the original audio remains playable locally.
- No voice recording is uploaded to the backend or exposed to department officers.

**Limits:** Browser speech recognition still depends on the browser/provider and may fail in some languages or after network failures. This does not add guaranteed long-form transcription for all 22 Indian languages. Original audio can be replayed locally regardless of language. Test on Chrome/Edge localhost and check for overlapping permissions or browser tab suspension.

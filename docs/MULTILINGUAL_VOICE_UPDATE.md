# CivicFlow voice update — experimental free-first build

## Changes
- `frontend/js/voice_support.js`: waits for browser voices, selects only matching-language voices, falls back to `/voice/speak` when unavailable or playback fails, checks audio errors, obtains user consent before external transmission.
- `backend/app/routes/voice_routes.py`: discovers edge-tts voice locales at runtime with a one-hour cache, only synthesizes when an exact locale is advertised; preserves legacy `/voice/odia`. `/voice/languages` lists the *currently available online* locales.
- `frontend/js/complaint.js`: permits recording attempts for all 22 scheduled-language choices, clearly states that browser recognition can be unsupported. Existing 14-language voice selection retained.

## Important limitations
- **Not a guarantee of working speech input, translation, or TTS in all 22 languages.** Unsupported voices return a clear error rather than speaking the wrong language. Speech input still relies on browser SpeechRecognition; browser availability varies. The broader language dropdown supports typed input, but not universal voice recognition.
- The online fallback uses the unofficial `edge-tts` package and an external internet-connected service; it may fail or change. Citizen complaint text is sent to that service *only after the user consents*. This is for demos and not approved for processing confidential production complaints.
- Ensure `backend/requirements.txt` has `edge-tts`, run `pip install -r requirements.txt`, then restart backend. Start frontend normally. No new API key needed.
- Test each language on your Windows/browser setup. Try Odia, Telugu, Hindi first. For 22-language coverage in production, provider-specific approved STT/TTS and real language tests are needed.
- Existing credentials intentionally excluded; keep your own private `.env` only locally.

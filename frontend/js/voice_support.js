(function () {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const base = () => window.CIVICFLOW_API_BASE ||
    (["localhost", "127.0.0.1"].includes(location.hostname) ? "http://127.0.0.1:8000" : "/api");
  let playbackGeneration = 0;
  let externalAudioConsent = false;

  async function browserVoices() {
    if (!("speechSynthesis" in window)) return [];
    const synth = window.speechSynthesis;
    const initial = synth.getVoices();
    if (initial.length) return initial;
    await new Promise(resolve => {
      const timeout = setTimeout(resolve, 1000);
      synth.addEventListener("voiceschanged", () => { clearTimeout(timeout); resolve(); }, { once: true });
    });
    return synth.getVoices();
  }

  function chooseVoice(voices, locale) {
    const code = String(locale).toLowerCase();
    const exact = voices.find(v => v.lang.toLowerCase() === code);
    // Prefer a match to the actual language, never fall back to English or Hindi.
    return exact || voices.find(v => v.lang.toLowerCase().split("-")[0] === code.split("-")[0]);
  }

  window.CivicFlowVoice = {
    supported: Boolean(SpeechRecognition),
    createRecognition(options = {}) {
      if (!SpeechRecognition) return null;
      const recognition = new SpeechRecognition();
      recognition.continuous = options.continuous ?? true;
      recognition.interimResults = options.interimResults ?? true;
      recognition.maxAlternatives = 1;
      recognition.lang = options.lang || "en-IN";
      return recognition;
    },
    async speak(text, lang = "en-IN") {
      if (!text || !text.trim()) return false;
      const generation = ++playbackGeneration;
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      if (this._audio) { this._audio.pause(); this._audio = null; }
      const voices = await browserVoices();
      const chosen = chooseVoice(voices, lang);
      if (chosen) {
        try {
          return await new Promise((resolve, reject) => {
            const utterance = new SpeechSynthesisUtterance(text);
            this._utterance = utterance; // Keep a reference to avoid speech cutoff.
            utterance.lang = chosen.lang;
            utterance.voice = chosen;
            utterance.rate = 0.95;
            utterance.onend = () => { this._utterance = null; resolve(true); };
            utterance.onerror = e => { this._utterance = null; reject(new Error(e.error || "Browser voice playback failed")); };
            if (generation !== playbackGeneration) return reject(new Error("Playback cancelled"));
            window.speechSynthesis.speak(utterance);
          });
        } catch (err) {
          console.warn("Browser voice failed; trying online same-language voice", err);
        }
      }
      if (generation !== playbackGeneration) throw new Error("Playback cancelled");
      return await this.speakOnline(text, lang, generation);
    },
    async speakOnline(text, lang, generation = playbackGeneration) {
      // Do not send citizen complaint text off-device without consent.
      if (!externalAudioConsent) {
        if (!window.confirm("This language needs online speech playback. The complaint text will be sent to an external speech provider. Continue?")) {
          throw new Error("Online playback cancelled. Your written complaint is unaffected.");
        }
        externalAudioConsent = true;
      }
      const response = await fetch(`${base()}/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 1800), lang })
      });
      if (!response.ok) {
        let message = `No supported voice was found for ${lang}. You can still read and submit the complaint.`;
        try { const d = await response.json(); message = typeof d.detail === "string" ? d.detail : message; } catch (_) {}
        throw new Error(message);
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error("The speech provider returned empty audio.");
      if (generation !== playbackGeneration) throw new Error("Playback cancelled");
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      this._audio = audio;
      try {
        await new Promise((resolve, reject) => {
          audio.onended = resolve;
          audio.onerror = () => reject(new Error("Unable to play this language's audio."));
          audio.play().catch(reject);
        });
        return true;
      } finally {
        URL.revokeObjectURL(url);
        if (this._audio === audio) this._audio = null;
      }
    },
    // Backward compatibility for other callers.
    speakOdiaOnline(text) { return this.speakOnline(text, "or-IN"); }
  };
})();

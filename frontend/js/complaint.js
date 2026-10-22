

// ============================================================
// Voice Complaint — description-first accessibility
// One complaint-language selector is shared by typing + voice.
// ============================================================
(function setupVoiceComplaint() {
    const button = document.getElementById("voiceStartBtn");
    const languageHint = document.getElementById("languageHint");
    const manualLanguageToggle = document.getElementById("manualLanguageToggle");
    const manualLanguageWrap = document.getElementById("manualLanguageWrap");
    const languageAutoLabel = document.getElementById("languageAutoLabel");
    const languageAutoNote = document.getElementById("languageAutoNote");
    const statusWrap = document.getElementById("voiceInlineStatus");
    const status = document.getElementById("voiceStatus");
    const statusDot = document.getElementById("voiceStatusDot");
    const preview = document.getElementById("voiceTranscriptPreview");
    const playback = document.getElementById("voicePlaybackBtn");
    const description = document.getElementById("description");
    const title = document.getElementById("title");

    if (!button || !description || !window.CivicFlowVoice) return;

    const languageToLocale = {
        en:"en-IN", hi:"hi-IN", te:"te-IN", or:"or-IN", bn:"bn-IN",
        ta:"ta-IN", kn:"kn-IN", ml:"ml-IN", mr:"mr-IN", gu:"gu-IN",
        pa:"pa-IN", ur:"ur-IN", as:"as-IN", ne:"ne-NP", brx:"brx-IN", doi:"doi-IN", ks:"ks-IN",
        kok:"kok-IN", mai:"mai-IN", mni:"mni-IN", sa:"sa-IN", sat:"sat-IN", sd:"sd-IN"
    };

    const languageNames = {
        en:"English", hi:"Hindi", te:"Telugu", or:"Odia", bn:"Bengali",
        ta:"Tamil", kn:"Kannada", ml:"Malayalam", mr:"Marathi", gu:"Gujarati",
        pa:"Punjabi", ur:"Urdu", as:"Assamese", ne:"Nepali", brx:"Bodo",
        doi:"Dogri", ks:"Kashmiri", kok:"Konkani", mai:"Maithili", mni:"Manipuri",
        sa:"Sanskrit", sat:"Santali", sd:"Sindhi"
    };

    const voiceSupportedLanguages = new Set(Object.keys(languageToLocale));

    function updateVoiceAvailability() {
        const selected = languageHint?.value || "auto";
        const note = document.getElementById("voiceLanguageRequiredNote");

        if (selected === "auto") {
            button.disabled = false;
            button.title = "Choose a language before recording.";
            if (note) note.hidden = true;
            return;
        }

        const supported = voiceSupportedLanguages.has(selected);
        button.disabled = !supported;

        if (supported) {
            button.innerHTML = '<i class="fa-solid fa-microphone"></i><span>Speak Complaint</span>';
            button.title = "Record complaint by voice";
            if (note) note.hidden = true;
        } else {
            button.innerHTML = '<i class="fa-solid fa-keyboard"></i><span>Voice unavailable</span>';
            button.title = "You can still type this complaint and CivicFlow will translate it.";
            if (note) {
                note.hidden = false;
                note.innerHTML = '<i class="fa-solid fa-circle-info"></i> Voice is not available for this language here. You can still type the complaint normally.';
            }
        }
    }

    const browserLocale =
        navigator.language && /^[a-z]{2,3}(-[A-Z]{2})?$/.test(navigator.language)
            ? navigator.language
            : "en-IN";

    function detectScriptLanguage(text) {
        if (/[\u0C00-\u0C7F]/.test(text)) return "te";
        if (/[\u0B00-\u0B7F]/.test(text)) return "or";
        if (/[\u0980-\u09FF]/.test(text)) return "bn";
        if (/[\u0B80-\u0BFF]/.test(text)) return "ta";
        if (/[\u0C80-\u0CFF]/.test(text)) return "kn";
        if (/[\u0D00-\u0D7F]/.test(text)) return "ml";
        if (/[\u0A80-\u0AFF]/.test(text)) return "gu";
        if (/[\u0A00-\u0A7F]/.test(text)) return "pa";
        if (/[\u0600-\u06FF]/.test(text)) return "ur";

        if (/[\u0900-\u097F]/.test(text)) {
            const base = browserLocale.split("-")[0].toLowerCase();
            if (["hi","mr","ne"].includes(base)) return base;
            return "hi";
        }
        return null;
    }

    function effectiveSpeechLocale() {
        const selected = languageHint?.value || "auto";
        if (selected === "auto") return null;
        return languageToLocale[selected] || null;
    }

    function updateLanguageStatus(code, source = "auto") {
        const detectedBadge = document.getElementById("voiceDetectedLanguage");
        const autoStatus = languageAutoLabel?.closest(".language-auto-status");

        if (detectedBadge) {
            if (source === "detected" && code && languageNames[code]) {
                detectedBadge.hidden = false;
                detectedBadge.textContent = `Detected: ${languageNames[code]}`;
            } else if (source === "manual" && code && languageNames[code]) {
                detectedBadge.hidden = false;
                detectedBadge.textContent = `Voice: ${languageNames[code]}`;
            } else {
                detectedBadge.hidden = true;
                detectedBadge.textContent = "";
            }
        }

        if (!languageAutoLabel || !languageAutoNote) return;
        if (source === "manual") {
            if (autoStatus) autoStatus.hidden = true;
            return;
        }
        if (autoStatus) autoStatus.hidden = false;
        if (!code || code === "auto") {
            languageAutoLabel.textContent = "Auto-detect";
            languageAutoNote.textContent = "CivicFlow will detect the language from your typed or spoken complaint.";
            return;
        }
        languageAutoLabel.textContent = languageNames[code] || code.toUpperCase();
        languageAutoNote.textContent = "Detected from the complaint transcript. You can change it manually if needed.";
    }

    let detectedVoiceLanguage = null;

    function syncDetectedLanguage(transcript) {
        const selected = languageHint?.value || "auto";

        if (selected !== "auto") {
            detectedVoiceLanguage = selected;
            updateLanguageStatus(selected, "manual");
            return selected;
        }

        const detected = detectScriptLanguage(transcript);
        detectedVoiceLanguage = detected || null;

        if (detectedVoiceLanguage) {
            updateLanguageStatus(detectedVoiceLanguage, "detected");
        } else {
            updateLanguageStatus("auto", "auto");
        }

        return detectedVoiceLanguage;
    }

    function playbackLocale() {
        const selected = languageHint?.value || "auto";
        const code = selected !== "auto" ? selected : detectedVoiceLanguage;
        return (code && languageToLocale[code]) ? languageToLocale[code] : browserLocale;
    }

    const picker = document.getElementById("languagePicker");
    const pickerButton = document.getElementById("languagePickerButton");
    const pickerPanel = document.getElementById("languagePickerPanel");
    const pickerValue = document.getElementById("languagePickerValue");
    const languageSearch = document.getElementById("languageSearch");
    const languageResults = document.getElementById("languageSearchResults");
    const allLanguages = Array.from(languageHint?.options || []).map(o => ({code:o.value,name:o.textContent.trim()}));

    function setPickerOpen(open) {
        if (!pickerPanel) return;
        pickerPanel.hidden = !open;
        pickerButton?.setAttribute("aria-expanded", String(open));
        if (open) {
            languageSearch.value = "";
            renderLanguageResults();
            languageSearch.focus();
        }
    }
    function renderLanguageResults() {
        if (!languageResults) return;
        const query = (languageSearch?.value || "").trim().toLocaleLowerCase();
        const matches = allLanguages.filter(o => o.name.toLocaleLowerCase().includes(query)).slice(0, 30);
        languageResults.replaceChildren();
        if (!matches.length) {
            const empty = document.createElement("p"); empty.className = "language-empty";
            empty.textContent = "No matching language."; languageResults.appendChild(empty);
            return;
        }
        matches.forEach(item => {
            const option = document.createElement("button");
            option.type = "button";
            option.className = "language-result";
            option.setAttribute("role", "option");
            option.setAttribute("aria-selected", String(languageHint.value === item.code));
            option.textContent = item.name;
            option.addEventListener("click", () => {
                languageHint.value = item.code;
                languageHint.dispatchEvent(new Event("change", {bubbles:true}));
                setPickerOpen(false);
                pickerButton.focus();
            });
            languageResults.appendChild(option);
        });
    }
    pickerButton?.addEventListener("click", () => setPickerOpen(pickerPanel.hidden));
    languageSearch?.addEventListener("input", renderLanguageResults);
    languageSearch?.addEventListener("keydown", evt => {
        if (evt.key === "Escape") { setPickerOpen(false); pickerButton.focus(); }
        if (evt.key === "Enter") {
            const first = languageResults.querySelector("button");
            if (first) {evt.preventDefault(); first.click();}
        }
    });
    document.addEventListener("pointerdown", evt => {
        if (picker && !picker.contains(evt.target)) setPickerOpen(false);
    });
    languageHint?.addEventListener("change", () => {
        if (pickerValue) pickerValue.textContent = languageHint.selectedOptions[0]?.textContent.trim() || "Auto-detect";
    });

    languageHint?.addEventListener("change", () => {
        updateVoiceAvailability();
        const note = document.getElementById("voiceLanguageRequiredNote");

        if (languageHint.value === "auto") {
            detectedVoiceLanguage = detectScriptLanguage(description.value || "");
            updateLanguageStatus(detectedVoiceLanguage || "auto", detectedVoiceLanguage ? "detected" : "auto");
            return;
        }

        if (note) note.hidden = true;
        detectedVoiceLanguage = languageHint.value;
        updateLanguageStatus(languageHint.value, "manual");
    });


    description.addEventListener("input", () => {
        if (languageHint?.value !== "auto") return;
        const detected = detectScriptLanguage(description.value);
        if (detected) updateLanguageStatus(detected, "detected");
    });

    function requireVoiceLanguage() {
        const selected = languageHint?.value || "auto";
        const note = document.getElementById("voiceLanguageRequiredNote");

        if (selected !== "auto") {
            if (!voiceSupportedLanguages.has(selected)) {
                if (note) {
                    note.hidden = false;
                    note.innerHTML = '<i class="fa-solid fa-circle-info"></i> Voice is not available for this language here. Please type the complaint instead.';
                }
                statusWrap.hidden = false;
                status.textContent = "Voice unavailable for this language";
                preview.textContent = "Typed complaints are still supported and will be translated normally.";
                return null;
            }
            if (note) note.hidden = true;
            return selected;
        }

        if (note) {
            note.hidden = false;
            note.classList.add("attention");
            setTimeout(() => note.classList.remove("attention"), 1400);
        }

        statusWrap.hidden = false;
        status.textContent = "Choose the spoken language first";
        preview.textContent = "Voice recording needs the language before listening so recognition and playback use the correct accent.";

        setPickerOpen(true);
        pickerButton?.scrollIntoView({ behavior:"smooth", block:"center" });
        return null;
    }

    updateVoiceAvailability();

    if (!window.CivicFlowVoice.supported) {
        button.disabled = true;
        button.innerHTML = '<i class="fa-solid fa-microphone-slash"></i><span>Voice unavailable</span>';
        button.title = "Voice input works best in Chrome or Edge.";
        return;
    }

    let recognition = null;
    let listening = false;
    let finalTranscript = "";
    let interimTranscript = "";
    let sessionNumber = 0;
    let restartTimer = null;
    let restartAttempts = 0;
    let stopping = false;
    let committedTranscript = false;
    // Audio is held only in this citizen's browser, never attached to submission.
    let microphoneStream = null;
    let recorder = null;
    let recordingParts = [];
    let recordedUrl = null;
    let playbackAudio = null;
    let recordingSession = 0;

    function discardRecording() {
        recordingSession++;
        if (playbackAudio) { playbackAudio.pause(); playbackAudio.src = ""; playbackAudio = null; }
        if (recordedUrl) { URL.revokeObjectURL(recordedUrl); recordedUrl = null; }
        if (recorder && recorder.state !== "inactive") {
            recorder.ondataavailable = null;
            recorder.onstop = null;
            try { recorder.stop(); } catch (_) {}
        }
        if (microphoneStream) microphoneStream.getTracks().forEach(track => track.stop());
        microphoneStream = null;
        recorder = null;
        recordingParts = [];
        playback.hidden = true;
    }

    async function startActualRecording() {
        discardRecording();
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
            throw new Error("Audio recording requires a recent Chrome/Edge browser on localhost or HTTPS.");
        }
        const session = recordingSession;
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (session !== recordingSession) { stream.getTracks().forEach(t => t.stop()); return false; }
        microphoneStream = stream;
        const media = new MediaRecorder(stream);
        recorder = media;
        media.ondataavailable = e => { if (session === recordingSession && e.data.size) recordingParts.push(e.data); };
        media.onstop = () => {
            stream.getTracks().forEach(t => t.stop());
            if (microphoneStream === stream) microphoneStream = null;
            if (session !== recordingSession) return;
            if (recordingParts.length) {
                const blob = new Blob(recordingParts, { type: media.mimeType || "audio/webm" });
                if (blob.size) {
                    recordedUrl = URL.createObjectURL(blob);
                    playback.hidden = false;
                    status.textContent = "Recording ready — Listen Back plays your own voice";
                }
            }
            recordingParts = [];
            recorder = null;
        };
        media.start(1000);
        return true;
    }

    function stopActualRecording() {
        if (recorder?.state === "recording") recorder.stop();
        else if (microphoneStream) {
            microphoneStream.getTracks().forEach(t => t.stop());
            microphoneStream = null;
        }
    }

    function setListening(active) {
        listening = active;
        button.classList.toggle("listening", active);
        statusDot.classList.toggle("listening", active);
        button.querySelector("span").textContent = active ? "Stop Listening" : "Speak Complaint";
        statusWrap.hidden = false;
        status.textContent = active ? "Recording — speak freely; click Stop Listening when finished" : "Voice ready";
    }

    function commitTranscript() {
        if (committedTranscript) return;
        committedTranscript = true;
        const clean = finalTranscript.trim();
        if (!clean) {
            status.textContent = "Recording finished. No speech was transcribed; listen back or type your complaint.";
            preview.textContent = "No recognized words — your original recording may still be played.";
            return;
        }
        syncDetectedLanguage(clean);
        const existing = description.value.trim();
        description.value = existing ? `${existing} ${clean}` : clean;
        description.dispatchEvent(new Event("input", { bubbles:true }));
        if (title && !title.value.trim()) {
            const firstSentence = clean.split(/[.!?।॥]/)[0].trim();
            title.value = (firstSentence || "Voice complaint").slice(0, 100);
            title.dispatchEvent(new Event("input", { bubbles:true }));
        }
        preview.textContent = clean;
        status.textContent = "Voice converted to text. Please review it before submitting.";
    }

    function endSession() {
        if (stopping) return;
        stopping = true;
        clearTimeout(restartTimer);
        setListening(false);
        // Preserve any finalized words even if the browser ended recognition unexpectedly.
        if (recognition) {
            try { recognition.stop(); } catch (_) {}
        }
        stopActualRecording();
        // onend will commit after pending final results; fallback covers a stalled onend.
        const session = sessionNumber;
        setTimeout(() => { if (sessionNumber === session) commitTranscript(); }, 500);
    }

    function startRecognition(session) {
        if (stopping || session !== sessionNumber) return;
        const speechLocale = effectiveSpeechLocale();
        const instance = window.CivicFlowVoice.createRecognition({
            lang: speechLocale, continuous: true, interimResults: true
        });
        if (!instance) { endSession(); return; }
        recognition = instance;
        // Each restarted recognizer starts result indices from zero.
        let processedFinals = new Set();
        instance.onstart = () => {
            if (session !== sessionNumber) return;
            restartAttempts = 0;
            status.textContent = "Recording — speak freely; click Stop Listening when finished";
        };
        instance.onresult = event => {
            if (session !== sessionNumber) return;
            let interim = "";
            for (let i = 0; i < event.results.length; i++) {
                const item = event.results[i];
                const words = item[0]?.transcript?.trim();
                if (!words) continue;
                if (item.isFinal) {
                    if (!processedFinals.has(i)) {
                        finalTranscript += `${words} `;
                        processedFinals.add(i);
                    }
                } else interim += `${words} `;
            }
            interimTranscript = interim;
            preview.textContent = (finalTranscript + interim).trim() || "Listening…";
        };
        instance.onerror = event => {
            if (session !== sessionNumber || stopping) return;
            console.warn("CivicFlow speech recognition:", event.error);
            if (["not-allowed", "service-not-allowed", "audio-capture", "language-not-supported"].includes(event.error)) {
                status.textContent = `Speech recognition unavailable (${event.error}). Your audio recording is preserved.`;
                endSession();
            } else if (event.error === "network") {
                status.textContent = "Speech recognition connection lost. Your audio recording is preserved.";
                endSession();
            } // no-speech and aborted can be transient and will retry from onend.
        };
        instance.onend = () => {
            if (session !== sessionNumber) return;
            if (stopping) { commitTranscript(); return; }
            // Chrome/Edge often ends SpeechRecognition at a silence boundary,
            // even with continuous=true. Keep MediaRecorder running and restart STT.
            status.textContent = "Still recording — reconnecting speech recognition…";
            restartAttempts += 1;
            if (restartAttempts > 12) {
                status.textContent = "Speech recognition repeatedly stopped. Audio is still available for Listen Back.";
                endSession();
                return;
            }
            restartTimer = setTimeout(() => startRecognition(session), Math.min(300 * restartAttempts, 1500));
        };
        try { instance.start(); }
        catch (error) {
            console.warn("Speech recognition restart failed:", error);
            restartAttempts += 1;
            if (restartAttempts > 12) endSession();
            else restartTimer = setTimeout(() => startRecognition(session), 600);
        }
    }

    button.addEventListener("click", async () => {
        if (listening) { endSession(); return; }
        const spokenLanguage = requireVoiceLanguage();
        if (!spokenLanguage || !effectiveSpeechLocale()) return;
        sessionNumber++;
        const session = sessionNumber;
        clearTimeout(restartTimer);
        stopping = false;
        committedTranscript = false;
        finalTranscript = "";
        interimTranscript = "";
        restartAttempts = 0;
        detectedVoiceLanguage = null;
        button.disabled = true;
        try {
            const ready = await startActualRecording();
            if (!ready || session !== sessionNumber) return;
            setListening(true);
            preview.textContent = "Speak naturally for as long as needed. Click Stop Listening when done.";
            startRecognition(session);
        } catch (error) {
            stopActualRecording();
            statusWrap.hidden = false;
            status.textContent = error.message || "Unable to record. Check microphone permission.";
            console.warn("Voice recording startup:", error);
        } finally { button.disabled = false; }
    });

    window.addEventListener("pagehide", () => {
        sessionNumber++;
        clearTimeout(restartTimer);
        if (recognition) { try { recognition.abort(); } catch (_) {} }
        discardRecording();
    });

    playback?.addEventListener("click", async () => {
        if (!recordedUrl || playback.disabled) {
            status.textContent = "Record your complaint first to hear your original voice.";
            return;
        }
        playback.disabled = true;
        statusWrap.hidden = false;
        status.textContent = "Playing your original recording...";
        try {
            if (playbackAudio) playbackAudio.pause();
            const audio = new Audio(recordedUrl);
            playbackAudio = audio;
            await new Promise((resolve, reject) => {
                audio.onended = resolve;
                audio.onerror = () => reject(new Error("Unable to play the recorded audio."));
                audio.play().catch(reject);
            });
            status.textContent = "Listen Back finished";
        } catch (error) {
            status.textContent = error.message || "Audio playback failed.";
        } finally {
            playbackAudio = null;
            playback.disabled = false;
        }
    });
})();


// complaint.js

const complaintMediaInput = document.getElementById("media");
complaintMediaInput?.addEventListener("change", () => {
    const preview = document.getElementById("mediaPreview");
    if (!preview) return;
    if (preview.dataset.objectUrl) URL.revokeObjectURL(preview.dataset.objectUrl);
    preview.replaceChildren();
    const file = complaintMediaInput.files?.[0];
    if (!file) { preview.hidden = true; return; }
    if (file.size > 50 * 1024 * 1024) {
        alert("Media must be 50 MB or smaller.");
        complaintMediaInput.value = "";
        preview.hidden = true;
        return;
    }
    const objectUrl = URL.createObjectURL(file);
    preview.dataset.objectUrl = objectUrl;
    let node;
    if (file.type.startsWith("video/")) {
        node = document.createElement("video");
        node.controls = true;
        node.preload = "metadata";
    } else if (file.type.startsWith("image/")) {
        node = document.createElement("img");
        node.alt = "Selected complaint media preview";
    } else {
        alert("Choose a supported JPG, PNG, MP4, MOV or AVI file.");
        complaintMediaInput.value = "";
        preview.hidden = true;
        return;
    }
    node.src = objectUrl;
    node.className = "complaint-media-preview__content";
    const caption = document.createElement("p");
    caption.textContent = `${file.name} · ${(file.size / (1024 * 1024)).toFixed(1)} MB`;
    preview.append(node, caption);
    preview.hidden = false;
});

let civicSubmitInFlight = false;
document.getElementById("complaintForm").addEventListener("submit", async function (e) {

    e.preventDefault();
    if (civicSubmitInFlight) return;

    const token = localStorage.getItem("access_token");

    if (!token) {
        alert("Please login first.");
        window.location.href = "login.html";
        return;
    }

    const formData = new FormData();

    const complaintTitle = document.getElementById("title").value.trim();
    const descriptionInput = document.getElementById("description").value.trim();
    const selectedMedia = document.getElementById("media").files[0];
    if (complaintTitle.length < 3) {
        alert("Add a short title or caption so the complaint can be routed correctly.");
        return;
    }
    if (!descriptionInput && !selectedMedia) {
        alert("Describe the issue, or attach a photo/video and add a short title or caption.");
        return;
    }
    formData.append("title", complaintTitle);
    // Video-first reports use their short caption as routing text. Staff still
    // review the media; CivicFlow does not claim to understand the video.
    formData.append("description", descriptionInput || complaintTitle);
    formData.append("language_hint", document.getElementById("languageHint")?.value || "auto");
    formData.append("state", document.getElementById("state").value);
    formData.append("district", document.getElementById("district").value);
    formData.append("area", document.getElementById("area").value);
    formData.append("address", document.getElementById("address").value);
    formData.append("landmark", document.getElementById("landmark").value);
    formData.append("pincode", document.getElementById("pincode").value);

    // formData.append(
    //     "latitude",
    //     document.getElementById("latitude").value || 0
    // );

    // formData.append(
    //     "longitude",
    //     document.getElementById("longitude").value || 0
    // );
    const lat = document.getElementById("latitude").value;
    const lon = document.getElementById("longitude").value;

    if (lat && lon) {
        formData.append("latitude", lat);
        formData.append("longitude", lon);
        formData.append("location_source", document.getElementById("locationSource")?.value || "gps");
    }

    const file = selectedMedia;

    if (file) {
        const allowed = new Set(["image/jpeg", "image/png", "video/mp4", "video/quicktime", "video/x-msvideo"]);
        if (!allowed.has(file.type)) {
            alert("Choose a JPG, PNG, MP4, MOV or AVI file.");
            return;
        }
        if (file.size > 50 * 1024 * 1024) {
            alert("Media must be 50 MB or smaller. You can submit without media and add evidence later.");
            return;
        }
        formData.append("file", file);
    }

    civicSubmitInFlight = true;
    const submitButton = this.querySelector('button[type="submit"], input[type="submit"]');
    if (submitButton) { submitButton.disabled = true; submitButton.dataset.oldLabel = submitButton.textContent; submitButton.textContent = "Submitting… please wait"; }
    try {

        const response = await fetch(`${API_BASE}/complaints`, {

            method: "POST",

            headers: {
                Authorization: `Bearer ${token}`
            },

            body: formData

        });

        const data = await response.json().catch(() => ({}));

        if (response.ok) {

            alert("Complaint Submitted Successfully!");

            document.getElementById("complaintForm").reset();

            window.location.href = "dashboard.html";

        } else {

            alert(data.detail || data.message || "Submission Failed");

        }

    } catch (err) {

        console.error("Complaint submission error:", err);

        alert("Unable to reach the CivicFlow server. Check My Complaints before retrying to avoid a duplicate submission.");

    } finally {
        civicSubmitInFlight = false;
        if (submitButton) { submitButton.disabled = false; submitButton.textContent = submitButton.dataset.oldLabel || "Submit Complaint"; }
    }

});
function goBack() {
    window.location.href = "dashboard.html";
}

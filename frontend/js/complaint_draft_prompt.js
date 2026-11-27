(() => {
  function currentDraftKey() {
    try {
      const token = localStorage.getItem("access_token") || "";
      const encoded = token.split(".")[1];
      if (!encoded) return null;
      const base64 = encoded.replace(/-/g, "+").replace(/_/g, "/");
      const payload = JSON.parse(atob(base64 + "=".repeat((4 - base64.length % 4) % 4)));
      const identity = String(payload.sub || "").trim().toLowerCase();
      if (!identity) return null;
      let hash = 2166136261;
      for (let i = 0; i < identity.length; i++) hash = Math.imul(hash ^ identity.charCodeAt(i), 16777619);
      return `civicflow:complaint-draft:${(hash >>> 0).toString(36)}`;
    } catch { return null; }
  }

  function initialize() {
    const key = currentDraftKey();
    if (!key) return;
    let draft;
    try { draft = JSON.parse(localStorage.getItem(key) || "null"); }
    catch { localStorage.removeItem(key); return; }
    if (!draft?.values) return;

    const params = new URLSearchParams(location.search);
    if (params.get("showComplaintDraft") !== "1") return;
    const prompt = document.getElementById("complaintDraftPrompt");
    const description = document.getElementById("complaintDraftDescription");
    const mediaNote = document.getElementById("complaintDraftMediaNote");
    if (!prompt) return;
    if (description && draft.savedAt) {
      const savedAt = new Date(draft.savedAt);
      if (!Number.isNaN(savedAt.getTime())) description.textContent = `You have a saved complaint from ${savedAt.toLocaleString()} that was not submitted. Would you like to continue it?`;
    }
    if (mediaNote) mediaNote.hidden = !draft.values.hadMedia;
    prompt.hidden = false;

    document.getElementById("restoreComplaintDraft")?.addEventListener("click", () => {
      prompt.hidden = true;
      const next = params.get("next");
      location.href = `complaint.html?resumeDraft=1${next === "lodge" ? "&next=lodge" : ""}`;
    }, { once: true });
    document.getElementById("discardComplaintDraft")?.addEventListener("click", () => {
      localStorage.removeItem(key);
      prompt.hidden = true;
      if (params.get("next") === "lodge") location.href = "complaint.html";
    }, { once: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
})();

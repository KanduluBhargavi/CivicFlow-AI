function escHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
const token = localStorage.getItem("access_token");

if (!token) {

    window.location.href = "login.html";

}

const params = new URLSearchParams(window.location.search);

const complaintId = params.get("id");


function formatFriendlyDate(value) {
    if (!value) return "Pending";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Pending" : date.toLocaleString();
}

function normalizeBadgeToken(value) {
    return String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

function setComplaintBadge(id, value, baseClass) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!value) {
        el.style.display = "none";
        el.textContent = "";
        el.className = `badge ${baseClass}`;
        return;
    }
    el.style.display = "inline-flex";
    el.textContent = value;
    el.className = `badge ${baseClass} ${normalizeBadgeToken(value)}`;
}

function firstMatchingTimelineDate(events, keywords = []) {
    const match = (events || []).find(evt => {
        const text = `${evt?.title || ""} ${evt?.detail || ""}`.toLowerCase();
        return keywords.some(keyword => text.includes(keyword));
    });
    return match?.created_at || null;
}

function renderComplaintTimeline(c) {
    const events = c?.action_timeline || [];
    const assignedAt = c.assigned_at || firstMatchingTimelineDate(events, ["assign", "assigned"]);
    const progressAt = c.in_progress_at || firstMatchingTimelineDate(events, ["in progress", "started", "work order", "field visit"]);
    const resolvedAt = c.resolved_at || firstMatchingTimelineDate(events, ["resolved", "closed", "completed"]);

    const assignedEl = document.getElementById("assignedAt");
    const progressEl = document.getElementById("progressAt");
    const resolvedEl = document.getElementById("resolvedAt");
    if (assignedEl) assignedEl.textContent = formatFriendlyDate(assignedAt);
    if (progressEl) progressEl.textContent = formatFriendlyDate(progressAt);
    if (resolvedEl) resolvedEl.textContent = formatFriendlyDate(resolvedAt);

    const timelineItems = document.querySelectorAll('.timeline-item');
    timelineItems.forEach(item => item.classList.remove('is-complete', 'is-pending'));
    if (timelineItems[0]) timelineItems[0].classList.add(assignedAt || c.assigned_officer ? 'is-complete' : 'is-pending');
    if (timelineItems[1]) timelineItems[1].classList.add(progressAt || ["In Progress", "Resolved"].includes(c.status) ? 'is-complete' : 'is-pending');
    if (timelineItems[2]) timelineItems[2].classList.add(resolvedAt || c.status === "Resolved" ? 'is-complete' : 'is-pending');
}

function conciseDuplicateReason(match) {
    const pct = Math.round(Math.max(0, Math.min(1, Number(match?.similarity) || 0)) * 100);
    const raw = String(match?.reason || '').replace(/\s+/g, ' ').trim();
    const candidate = String(match?.title || '').trim();
    const issue = candidate && candidate.toLowerCase() !== 'complaint' ? `Reported issue: ${candidate}. ` : '';
    // The score is semantic similarity, NOT evidence that two reports concern the same physical incident.
    return `${issue}Text similarity score: ${pct}%. Review the full description and locality before grouping or acting.`;
}

function renderDelayRequests(items = []) {
    const list = document.getElementById("delayRequestList");
    if (!list) return;
    if (!items.length) {
        list.innerHTML = '<p class="audit-note">No delay requests recorded.</p>';
        return;
    }
    list.innerHTML = items.map(item => {
        const pending = item.status === "Pending Head Review";
        return `<article class="delay-request-card">
            <strong>${escHtml(item.status)} · ${escHtml(String(item.blocker_category || "other").replaceAll("_", " "))}</strong>
            <p>${escHtml(item.reason)}</p>
            <small>Requested follow-up: ${item.requested_until ? new Date(item.requested_until).toLocaleString() : "Not provided"} · Submitted ${item.created_at ? new Date(item.created_at).toLocaleString() : ""}</small>
            ${item.manager_note ? `<p><b>Head's note:</b> ${escHtml(item.manager_note)}</p>` : ""}
            ${!isOfficer && pending ? `<div class="delay-request-actions"><input type="text" id="delay-review-note-${item.request_id}" placeholder="Decision note (required if declining)"><div class="delay-review-actions"><button type="button" data-delay-decision="approve" data-delay-id="${item.request_id}">Approve until requested time</button><button type="button" class="decline" data-delay-decision="decline" data-delay-id="${item.request_id}">Decline</button></div></div>` : ""}
        </article>`;
    }).join("");
}


const actualRole = (localStorage.getItem("actual_role") || "manager").toLowerCase();
const isOfficer = actualRole === "officer";

function renderOriginalFieldNote(elementId, originalValue, englishValue) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const old = el.parentElement?.querySelector(`.original-field-note[data-for="${elementId}"]`);
    if (old) old.remove();

    if (originalValue && englishValue && originalValue !== englishValue) {
        const note = document.createElement("small");
        note.className = "original-field-note";
        note.dataset.for = elementId;
        note.textContent = `Original: ${originalValue}`;
        el.insertAdjacentElement("afterend", note);
    }
}

function applyRolePermissions() {
    document.querySelectorAll(".manager-only").forEach(el => el.style.display = isOfficer ? "none" : "");
    document.querySelectorAll(".officer-only").forEach(el => el.style.display = isOfficer ? "" : "none");
    const roleText = document.getElementById("roleContextText");
    const briefTitle = document.getElementById("briefTitle");
    const actionRow = document.getElementById("recommendedActionRow");
    if (isOfficer) {
        if (roleText) roleText.textContent = `Officer workspace — ${localStorage.getItem("name") || "Assigned Officer"}. Operational actions and status updates are your responsibility.`;
        if (briefTitle) briefTitle.textContent = "AI Officer Brief";
        if (actionRow) actionRow.style.display = "flex";
    } else {
        if (roleText) roleText.textContent = "Department Head workspace — assignment, SLA oversight, workload management and routing decisions.";
        if (briefTitle) briefTitle.textContent = "Complaint Intelligence";
        if (actionRow) actionRow.style.display = "none";
    }
}
applyRolePermissions();

// ===============================
// Load Complaint
// ===============================


function renderSemanticMatches(data) {
    const duplicateSection = document.getElementById("duplicateSection");
    const duplicateList = document.getElementById("duplicateList");
    const duplicateAnalysis = document.getElementById("duplicateAnalysis");
    if (!duplicateSection || !duplicateList || !duplicateAnalysis) return;

    const duplicateGroup = data?.duplicate_group || [];
    const da = data?.duplicate_analysis || {};
    const incidentReports = Number(data?.incident_total_reports || 1);

    duplicateList.innerHTML = "";
    duplicateAnalysis.innerHTML = "";

    if (!duplicateGroup.length) {
        duplicateSection.style.display = "none";
        return;
    }

    duplicateSection.style.display = "block";
    const label = isOfficer
        ? `Direct semantic matches assigned to you · ${duplicateGroup.length}`
        : `Direct semantic matches · ${duplicateGroup.length}`;

    duplicateAnalysis.innerHTML = `
        <div class="dup-score-card">
            <strong>${label}</strong>
            <span class="dup-cluster-note">${isOfficer
                ? "Only direct text matches assigned to your account are shown. This count is separate from the larger linked-incident total."
                : "These are direct Sentence-BERT matches to this complaint. Similarity is pairwise, not a transitive cluster."}</span>
            <span><b>${duplicateGroup.length} direct text match(es)</b></span>
            <span>${incidentReports} report(s) are linked in the persisted incident cluster. The ${duplicateGroup.length} cards below are only the direct text matches for this complaint; clusters can include reports linked through other direct matches.</span>
            <span>These suggestions compare meaning, not proof of the same incident. Confirm issue type and location before grouping.</span>
        </div>`;

    duplicateGroup.forEach(d => {
        const card = document.createElement("a");
        card.className = "related-complaint-card";
        card.href = `department_complaint_details.html?id=${d.complaint_id}`;
        const pct = Math.round((d.similarity || 0) * 100);
        card.innerHTML = `
            <div class="related-complaint-head related-complaint-card__top">
                <strong>#${d.complaint_id} · ${escHtml(d.title || "Complaint")}</strong>
                <span>${pct}% similar</span>
            </div>
            <p class="related-why">${conciseDuplicateReason(d)}</p>
            <small>${[d.priority || "", d.status || ""].filter(Boolean).join(" · ")}</small>
        `;
        duplicateList.appendChild(card);
    });
}

async function loadSemanticMatches() {
    const duplicateSection = document.getElementById("duplicateSection");
    const duplicateAnalysis = document.getElementById("duplicateAnalysis");

    try {
        if (duplicateSection && duplicateAnalysis) {
            duplicateSection.style.display = "block";
            duplicateAnalysis.innerHTML = `
                <div class="dup-score-card">
                    <strong>Checking similar complaints…</strong>
                    <span>This AI section loads separately so complaint details stay fast.</span>
                </div>`;
        }

        const response = await fetch(
            `${API_BASE}/department/complaint/${complaintId}/semantic-matches`,
            { headers: { Authorization: `Bearer ${token}` } }
        );

        if (!response.ok) {
            if (duplicateSection) duplicateSection.style.display = "none";
            return;
        }

        const data = await response.json();
        renderSemanticMatches(data);
    } catch (err) {
        console.log("Semantic match load error", err);
        if (duplicateSection) duplicateSection.style.display = "none";
    }
}


function humanizeDecisionLabel(value) {
    return String(value || "")
        .replace(/[_-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/\b\w/g, letter => letter.toUpperCase());
}

function setDecisionText(id, value, fallback = "-") {
    const element = document.getElementById(id);
    if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value);
}

function renderTranslationFeedback(items = []) {
    const panel = document.getElementById("translationFeedbackPanel");
    const list = document.getElementById("translationFeedbackList");
    if (!panel || !list) return;
    panel.style.display = items.length ? "block" : "none";
    list.replaceChildren();
    items.forEach(item => {
        const card = document.createElement("article");
        card.className = "translation-feedback-item";
        card.innerHTML = `<strong>${escHtml(item.status)} feedback · ${formatFriendlyDate(item.created_at)}</strong>
            <p>${escHtml(item.note)}</p>${item.suggested_english ? `<p><b>Suggested English:</b> ${escHtml(item.suggested_english)}</p>` : ""}
            ${item.review_note ? `<p><b>Review note:</b> ${escHtml(item.review_note)}</p>` : ""}`;
        if (!isOfficer && item.status === "Open") {
            const note = document.createElement("textarea");
            note.maxLength = 1000;
            note.placeholder = "Optional note for the citizen";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "review-translation-feedback-btn";
            button.textContent = "Mark reviewed";
            button.addEventListener("click", async () => {
                button.disabled = true;
                try {
                    const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/translation-feedback/${item.feedback_id}/review`, {
                        method: "POST",
                        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                        body: JSON.stringify({ review_note: note.value.trim() || null })
                    });
                    if (!response.ok) throw new Error("Unable to update feedback.");
                    await loadComplaint();
                } catch (error) {
                    alert(error.message);
                    button.disabled = false;
                }
            });
            card.append(note, button);
        }
        list.appendChild(card);
    });
}

function appendDecisionFlag(container, label, kind = "neutral") {
    const flag = document.createElement("span");
    flag.className = `ai-decision-flag ai-decision-flag--${kind}`;
    flag.textContent = label;
    container.appendChild(flag);
}

function renderPriorityExplanation(analysis, complaint) {
    const panel = document.getElementById("aiDecisionPanel");
    if (!panel) return;

    const data = analysis && typeof analysis === "object" ? analysis : {};
    const basePriority = data.ml_base_priority || complaint.base_priority || "Unavailable";
    const finalPriority = data.priority || complaint.priority || "Unknown";
    const scoreValue = data.score !== null && data.score !== undefined && Number.isFinite(Number(data.score))
        ? Number(data.score).toFixed(1) : null;
    const confidenceValue = data.ml_confidence ?? complaint.priority_confidence;
    const confidenceText = confidenceValue !== null && confidenceValue !== undefined && Number.isFinite(Number(confidenceValue))
        ? `${Math.round(Number(confidenceValue) * 100)}%` : "Unavailable";

    setDecisionText("aiBasePriority", basePriority);
    setDecisionText("aiFinalPriority", finalPriority);
    setDecisionText("aiPriorityScore", scoreValue === null ? "Unavailable" : `${scoreValue} / 100`);
    setDecisionText("aiPriorityConfidence", confidenceText);
    setDecisionText("aiPriorityReason", data.reason || complaint.priority_reason || "No explanation was recorded.");

    const status = document.getElementById("aiReviewStatus");
    if (status) {
        const needsReview = Boolean(data.needs_human_review);
        const safetyApplied = Boolean(data.critical_override || data.high_risk_floor || data.verified_emergency);
        status.textContent = needsReview ? "Human review recommended" : safetyApplied ? "Safety signal present" : "Model-assisted decision";
        status.className = `ai-decision-status ${needsReview ? "is-review" : safetyApplied ? "is-safety" : "is-normal"}`;
    }

    const flags = document.getElementById("aiSafetyFlags");
    if (flags) {
        flags.replaceChildren();
        if (data.critical_override) appendDecisionFlag(flags, "Critical text-safety override", "danger");
        if (data.high_risk_floor) appendDecisionFlag(flags, "High-risk safety floor applied", "warning");
        if (data.verified_emergency) appendDecisionFlag(flags, "Emergency verified", "danger");
        if (data.needs_human_review) appendDecisionFlag(flags, "Low model confidence: verify manually", "warning");
        if (!flags.childElementCount) appendDecisionFlag(flags, "No saved safety override or verified emergency flag", "neutral");
    }

    const factorContainer = document.getElementById("aiPriorityFactors");
    if (factorContainer) {
        factorContainer.replaceChildren();
        const factors = Array.isArray(data.factors) ? data.factors : [];
        if (!factors.length) {
            const empty = document.createElement("p");
            empty.className = "audit-note";
            empty.textContent = "No contributing factors were recorded in the current priority breakdown.";
            factorContainer.appendChild(empty);
        } else {
            factors.forEach(item => {
                const row = document.createElement("div");
                row.className = "ai-factor-row";
                const copy = document.createElement("div");
                copy.className = "ai-factor-copy";
                const title = document.createElement("strong");
                title.textContent = item.factor === "Similar complaints" ? "Linked incident reports" : (item.factor || "Priority factor");
                const detail = document.createElement("p");
                detail.textContent = item.factor === "Similar complaints"
                    ? `${item.detail || "Incident cluster report count."} This is a linked-cluster count, not the direct semantic-match count.`
                    : (item.detail || "No additional detail recorded.");
                copy.append(title, detail);
                const points = document.createElement("span");
                const n = Number(item.points);
                points.className = `ai-factor-points ${Number.isFinite(n) && n < 0 ? "is-negative" : ""}`;
                points.textContent = Number.isFinite(n) ? `${n > 0 ? "+" : ""}${n.toFixed(1)}` : "—";
                row.append(copy, points);
                factorContainer.appendChild(row);
            });
        }
    }

    const adjustmentList = document.getElementById("aiLabelAdjustments");
    if (adjustmentList) {
        adjustmentList.replaceChildren();
        const adjustments = Array.isArray(data.label_adjustments) ? data.label_adjustments : [];
        if (!adjustments.length) {
            const item = document.createElement("li");
            item.textContent = "No label adjustment recorded.";
            adjustmentList.appendChild(item);
        } else {
            adjustments.forEach(adjustment => {
                const item = document.createElement("li");
                item.textContent = humanizeDecisionLabel(adjustment);
                adjustmentList.appendChild(item);
            });
        }
    }

    const band = data.score_band ? `Score band: ${data.score_band}` : "Score band unavailable";
    const updated = data.updated_at ? `Last priority recalculation: ${new Date(data.updated_at).toLocaleString()} · ${band}` : band;
    setDecisionText("aiPriorityUpdated", updated, "");
}

async function loadComplaint() {

    try {

        const response = await fetch(

            `${API_BASE}/department/complaint/${complaintId}`,

            {

                headers: {

                    Authorization: `Bearer ${token}`

                }

            }

        );

        if (!response.ok) {

            alert("Unable to load complaint.");

            return;

        }

        const c = await response.json();
        renderTranslationFeedback(c.translation_feedback || []);

        const assigneeChip = document.getElementById("currentAssignee");
        if (assigneeChip) assigneeChip.textContent = c.assigned_officer ? `Assigned to ${c.assigned_officer.name}` : "Unassigned";
        populateOfficerAssignment(c.assigned_officer).catch(err => console.log('Assignment options load error', err));

        document.getElementById("complaintId").textContent =
            c.complaint_id;

        document.getElementById("title").textContent = c.title;
        renderOriginalFieldNote("title", c.original_title, c.title);

        document.getElementById("description").textContent =
            c.description;

        const translatedEl = document.getElementById("translatedText");
        const translationNote = document.getElementById("translationNote");
        const translationBlock = document.getElementById("translationBlock");
        const isEnglishComplaint = (c.language || "").toLowerCase() === "english" || c.translation_status === "original_english";
        if (translationBlock) translationBlock.style.display = isEnglishComplaint ? "none" : "block";
        if (!isEnglishComplaint && translatedEl) {
            translatedEl.textContent = c.translated_text || "AI English translation unavailable.";
            translatedEl.classList.toggle("translation-unavailable", !c.translated_text);
        }
        if (!isEnglishComplaint && translationNote) {
            translationNote.textContent = c.translated_text
                ? "English processing copy used for routing, priority and summary."
                : "AI translation is temporarily unavailable for this complaint.";
        }

        document.getElementById("summary").textContent =
            c.ai_summary || "No AI Summary";

        document.getElementById("state").textContent =
            c.state;

        document.getElementById("district").textContent =
            c.district;

        document.getElementById("area").textContent = c.area;
        renderOriginalFieldNote("area", c.original_area, c.area);

        document.getElementById("address").textContent = c.address;
        renderOriginalFieldNote("address", c.original_address, c.address);

        document.getElementById("landmark").textContent = c.landmark || "-";
        renderOriginalFieldNote("landmark", c.original_landmark, c.landmark);

        document.getElementById("pincode").textContent =
            c.pincode;

        document.getElementById("createdAt").textContent =
            new Date(c.created_at).toLocaleString();

        document.getElementById("language").textContent =
            c.language || "Unknown";

        setComplaintBadge("priority", c.priority || "Unknown", "priority");
        setComplaintBadge("status", c.display_status || c.status || "Unknown", "status");
        const sentimentValue = c.sentiment || c.ai_sentiment || c.citizen_sentiment || "";
        setComplaintBadge("sentiment", sentimentValue, "sentiment");
        renderComplaintTimeline(c);

        // AI Officer Brief
        const brief = c.officer_brief || {};
        document.getElementById("briefIssue").textContent = brief.issue || "-";
        document.getElementById("briefRisk").textContent = brief.risk || "-";
        document.getElementById("briefDuplicates").textContent = brief.duplicate_context || "-";
        document.getElementById("briefAction").textContent = brief.next_action || "-";

        // Explainable AI: render the persisted dynamic priority breakdown returned by the API.
        renderPriorityExplanation(c.priority_analysis, c);

        // SLA/deadline monitoring
        const sla = c.sla || {};
        const slaState = document.getElementById("slaState");
        slaState.textContent = sla.state || "Unknown";
        slaState.className = `sla-state ${(sla.state || "unknown").toLowerCase().replace(" ", "-")}`;
        document.getElementById("slaTarget").textContent = sla.target_hours != null ? `${sla.target_hours} hours` : "Department assessment needed";
        document.getElementById("slaDeadline").textContent = sla.deadline ? new Date(sla.deadline).toLocaleString() : "Pending assessment";
        const assignmentDue = document.getElementById("officerAssignmentDue");
        if (assignmentDue) {
            assignmentDue.textContent = c.officer_assignment_due_at
                ? new Date(c.officer_assignment_due_at).toLocaleString()
                : "Waiting for department receipt";
        }
        const slaBasis = document.getElementById("slaBasis");
        if (slaBasis) {
            if (sla.state === "Approved Extension" && sla.extension_until) {
                slaBasis.textContent = `The Department Head approved a quiet follow-up window until ${new Date(sla.extension_until).toLocaleString()}. The original resolution target remains in the audit history; reminders resume if the follow-up is missed.`;
            } else {
            const basisLabels = {
                similar_department_priority_text: "similar resolved complaints in this department, matched by priority and issue text",
                department_priority_history: "resolved complaints with this priority in this department",
                similar_cross_department_priority_history: "similar resolved complaints across departments, matched by priority and issue text",
                cross_department_priority_history: "resolved complaints with this priority across departments",
                limited_historical_estimate: "the available resolved-complaint history",
                initial_text_priority_estimate: "an initial issue-type, complexity and priority assessment; past case data will refine future estimates"
            };
            const range = sla.lower_hours != null && sla.upper_hours != null
                ? ` Typical past range: ${sla.lower_hours}–${sla.upper_hours} hours.` : "";
            const source = basisLabels[sla.basis] || "available complaint and resolution information";
            slaBasis.textContent = `Planning estimate based on ${source}${sla.sample_size ? ` (${sla.sample_size} completed cases)` : ""}.${range} It is not a guarantee; each completed case helps improve future estimates. The officer-assignment timer below is separate.`;
            }
        }
        if (typeof sla.remaining_minutes === "number") {
            const mins = sla.remaining_minutes;
            const abs = Math.abs(mins);
            const h = Math.floor(abs / 60);
            const m = abs % 60;
            document.getElementById("slaRemaining").textContent = mins >= 0 ? `${h}h ${m}m` : `Breached by ${h}h ${m}m`;
        } else {
            document.getElementById("slaRemaining").textContent = "-";
        }
        document.getElementById("slaProgress").style.width = `${Math.min(100, sla.progress_percent || 0)}%`;

        // Auditable action timeline
        const timeline = document.getElementById("actionTimeline");
        const events = c.action_timeline || [];
        renderDelayRequests(c.delay_requests || []);
        timeline.innerHTML = events.length ? events.map(e => `
            <div class="action-event">
                <div><strong>${escHtml(e.title)}</strong><span>${escHtml(e.actor || "System")}</span></div>
                <p>${escHtml(e.detail || "")}</p>
                <time>${e.created_at ? new Date(e.created_at).toLocaleString() : ""}</time>
            </div>`).join("") : `<p class="audit-note">No audit events recorded yet.</p>`;

        // Semantic matches load separately so the complaint itself appears instantly.
        renderSemanticMatches(c);
        loadSemanticMatches();

        // Media
        // ===========================

        const media =
            document.getElementById("mediaContainer");

        if (c.media_url) {

            const extension =
                c.media_url.split("?")[0].split(".").pop().toLowerCase();

            if (

                extension === "jpg" ||

                extension === "jpeg" ||

                extension === "png"

            ) {

                media.innerHTML = `

                <img
                src="${API_BASE}/${c.media_url}">

                `;

            }

            else {

                media.innerHTML = `

                <video controls>

                <source
                src="${API_BASE}/${c.media_url}">

                </video>

                `;

            }

        }

        else {

            media.innerHTML =
                "<p>No Media Uploaded.</p>";

        }

    }

    catch (err) {

        console.error("Complaint details unavailable:",err);
        const heading = document.getElementById("title");
        if (heading && heading.textContent === "Loading...") heading.textContent = "Unable to load complaint";

    }

}

// ===============================
// Update Status
// ===============================

document.getElementById("updateStatusBtn")

.addEventListener("click",

async function () {

    const status =

    document.getElementById("newStatus").value;

    const response = await fetch(

        `${API_BASE}/department/update-status/${complaintId}`,

        {

            method: "PUT",

            headers: {

                Authorization: `Bearer ${token}`,

                "Content-Type": "application/json"

            },

            body: JSON.stringify({
                status: status,
                note: document.getElementById("statusNote").value.trim() || null
            })

        }

    );

    const data = await response.json();
    alert(data.message || data.detail || "Unable to update status");
    if (response.ok) loadComplaint();

});

loadComplaint();

// AI reroute suggestion controls were removed from the UI.
// Incorrect Routing Recovery below is the single Department Head correction flow.

// ===============================
// Record accountable officer action
// ===============================
document.getElementById("addActionBtn").addEventListener("click", async function () {
    const note = document.getElementById("actionNote").value.trim();
    const actionType = document.getElementById("actionType").value;
    if (!note) {
        alert("Please enter an action note.");
        return;
    }
    const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/action`, {
        method: "POST",
        headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ action_type: actionType, note })
    });
    const data = await response.json();
    alert(data.message || data.detail || "Action recorded");
    if (response.ok) {
        document.getElementById("actionNote").value = "";
        loadComplaint();
    }
});

const submitDelayRequestBtn = document.getElementById("submitDelayRequestBtn");
if (submitDelayRequestBtn) submitDelayRequestBtn.addEventListener("click", async () => {
    const reason = document.getElementById("delayReason").value.trim();
    const localUntil = document.getElementById("delayRequestedUntil").value;
    const result = document.getElementById("delayRequestResult");
    if (reason.length < 12 || !localUntil) {
        result.textContent = "Explain work completed and the blocker, then choose a follow-up time.";
        return;
    }
    const requestedUntil = new Date(localUntil);
    if (Number.isNaN(requestedUntil.getTime()) || requestedUntil <= new Date()) {
        result.textContent = "Choose a follow-up time in the future.";
        return;
    }
    submitDelayRequestBtn.disabled = true;
    result.textContent = "Sending the request to the Department Head…";
    try {
        const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/delay-request`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            body: JSON.stringify({
                reason,
                blocker_category: document.getElementById("delayBlocker").value,
                requested_until: requestedUntil.toISOString()
            })
        });
        const data = await response.json();
        result.textContent = data.message || data.detail || "Unable to submit the delay request.";
        if (response.ok) {
            document.getElementById("delayReason").value = "";
            document.getElementById("delayRequestedUntil").value = "";
            loadComplaint();
        }
    } catch (_) {
        result.textContent = "Could not reach CivicFlow. Your request was not confirmed; please retry.";
    } finally {
        submitDelayRequestBtn.disabled = false;
    }
});

document.getElementById("delayRequestList")?.addEventListener("click", async event => {
    const button = event.target.closest("[data-delay-decision]");
    if (!button) return;
    const decision = button.dataset.delayDecision;
    const requestId = button.dataset.delayId;
    const noteInput = document.getElementById(`delay-review-note-${requestId}`);
    const note = noteInput?.value.trim() || "";
    if (decision === "decline" && note.length < 5) {
        alert("Add a brief reason before declining this request.");
        noteInput?.focus();
        return;
    }
    if (decision === "approve" && !confirm("Approve the requested follow-up time? The original target will remain in the audit history.")) return;
    button.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/delay-request/${requestId}`, {
            method: "PUT",
            headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            body: JSON.stringify({ decision, note })
        });
        const data = await response.json();
        if (!response.ok) alert(data.detail || "Unable to review the delay request.");
        else loadComplaint();
    } catch (_) {
        alert("Could not reach CivicFlow. The request may still be pending.");
    } finally {
        button.disabled = false;
    }
});

// ===============================
// Individual Officer Assignment
// ===============================
async function populateOfficerAssignment(currentAssignee) {
    const controls = document.getElementById("managerAssignmentControls");
    const select = document.getElementById("officerSelect");
    if (!controls || !select) return;
    if (localStorage.getItem("actual_role") === "officer") {
        controls.style.display = "none";
        return;
    }
    const changeBtn = document.getElementById("changeAssignmentBtn");
    const cancelBtn = document.getElementById("cancelAssignmentChangeBtn");
    const recommendedBtn = document.getElementById("assignRecommendedBtn");
    const selectedBtn = document.getElementById("assignOfficerBtn");
    const alreadyAssigned = Boolean(currentAssignee);
    controls.hidden = alreadyAssigned;
    if (changeBtn) {
        changeBtn.hidden = !alreadyAssigned;
        changeBtn.setAttribute("aria-expanded", "false");
    }
    if (cancelBtn) cancelBtn.hidden = true;
    if (recommendedBtn) recommendedBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> ${alreadyAssigned ? "Reassign Recommended" : "Assign Recommended"}`;
    if (selectedBtn) selectedBtn.innerHTML = `<i class="fa-solid fa-user-plus"></i> ${alreadyAssigned ? "Reassign Selected" : "Assign Selected"}`;
    try {
        const response = await fetch(`${API_BASE}/department/officers`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok) return;
        const officers = await response.json();
        select.innerHTML = '<option value="">Select officer</option>' + officers.map(o =>
            `<option value="${o.user_id}" ${currentAssignee && currentAssignee.user_id === o.user_id ? "selected" : ""}>${escHtml(o.name)} — ${o.assigned} assigned</option>`
        ).join("");
        if (changeBtn) {
            changeBtn.hidden = !alreadyAssigned;
            controls.hidden = alreadyAssigned;
            changeBtn.setAttribute("aria-expanded", "false");
            if (cancelBtn) cancelBtn.hidden = true;
        }
    } catch (err) {
        console.log("Officer list load error", err);
    }
}

async function assignOfficer() {
    const officerId = document.getElementById("officerSelect")?.value;
    if (!officerId) {
        alert("Select an officer first.");
        return;
    }
    const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/assign-officer/${officerId}`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` }
    });
    const data = await response.json();
    if (!response.ok) {
        alert(data.detail || "Unable to assign officer");
        return;
    }
    alert(data.message);
    loadComplaint();
}

async function loadOfficerRecommendations() {
    const box = document.getElementById("smartOfficerRecommendation");
    if (!box || localStorage.getItem("actual_role") === "officer") {
        if (box) box.style.display = "none";
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/officer-recommendations`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        const data = await response.json();
        if (!response.ok) {
            box.innerHTML = `<span>No recommendation available.</span>`;
            return;
        }
        if (!data.recommended) {
            box.innerHTML = `<strong>No eligible officer is posted in this complaint's state.</strong><br><small>Add or reactivate a local officer from the Department Dashboard. A Department Head can still make a manual exception.</small>`;
            return;
        }
        const r = data.recommended;
        box.innerHTML = `
            <div><strong><i class="fa-solid fa-wand-magic-sparkles"></i> Recommended: ${escHtml(r.name)}</strong>
            <span class="review-chip">Suitability score: ${Number(r.fit_score || 0).toFixed(1)}/100</span></div>
            <p>${escHtml([r.area, r.district, r.state].filter(Boolean).join(', ') || 'General coverage')} • ${escHtml(r.specialization || 'General')} • ${r.active_cases}/${r.max_active_cases} active cases</p>
            <small>This is a routing suitability score, not a guarantee of individual skill. It weighs posting, specialization, workload, capacity, SLA history and past performance. ${r.performance_index == null ? 'No historical performance data yet.' : `Historical performance index: ${Number(r.performance_index).toFixed(1)}/100.`} ${(r.reasons || []).map(escHtml).join(' • ')}</small>
        `;
    } catch (err) {
        box.innerHTML = `<span>Recommendation temporarily unavailable.</span>`;
    }
}

async function assignRecommendedOfficer() {
    const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/assign-recommended`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
    });
    const data = await response.json();
    if (!response.ok) return alert(data.detail || "Unable to assign recommended officer");
    alert(data.message);
    loadComplaint();
    loadOfficerRecommendations();
}

const assignRecommendedBtn = document.getElementById("assignRecommendedBtn");
if (assignRecommendedBtn) assignRecommendedBtn.addEventListener("click", assignRecommendedOfficer);
const assignOfficerBtn = document.getElementById("assignOfficerBtn");
if (assignOfficerBtn) assignOfficerBtn.addEventListener("click", assignOfficer);
const changeAssignmentBtn = document.getElementById("changeAssignmentBtn");
if (changeAssignmentBtn) changeAssignmentBtn.addEventListener("click", () => {
    const controls = document.getElementById("managerAssignmentControls");
    if (!controls) return;
    controls.hidden = false;
    changeAssignmentBtn.hidden = true;
    const cancel = document.getElementById("cancelAssignmentChangeBtn");
    if (cancel) cancel.hidden = false;
    changeAssignmentBtn.setAttribute("aria-expanded", "true");
    controls.querySelector("select")?.focus();
});
const cancelAssignmentChangeBtn = document.getElementById("cancelAssignmentChangeBtn");
if (cancelAssignmentChangeBtn) cancelAssignmentChangeBtn.addEventListener("click", () => {
    const controls = document.getElementById("managerAssignmentControls");
    if (controls) controls.hidden = true;
    cancelAssignmentChangeBtn.hidden = true;
    if (changeAssignmentBtn) {
        changeAssignmentBtn.hidden = false;
        changeAssignmentBtn.setAttribute("aria-expanded", "false");
    }
});
loadOfficerRecommendations();

const proofBtn=document.getElementById("uploadResolutionProofBtn");
if(proofBtn){proofBtn.addEventListener("click",async()=>{
  const file=document.getElementById("resolutionProofFile").files[0];
  const note=document.getElementById("resolutionProofNote").value.trim();
  if(!file||!note){alert("Select an after-photo and enter a resolution note.");return;}
  const fd=new FormData(); fd.append("proof",file); fd.append("note",note);
  const response=await fetch(`${API_BASE}/department/complaint/${complaintId}/resolution-proof`,{method:"POST",headers:{Authorization:`Bearer ${token}`},body:fd});
  const data=await response.json(); alert(data.message||data.detail); if(response.ok) loadComplaint();
});}

// ===============================
// AI translation + manual routing recovery
// ===============================
function apiMessage(data, fallback) {
    if (!data) return fallback;
    if (typeof data.message === "string") return data.message;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map(item => item.msg || JSON.stringify(item)).join("; ");
    if (data.detail && typeof data.detail === "object") return data.detail.message || JSON.stringify(data.detail);
    return fallback;
}

async function loadTransferDepartments() {
    const select = document.getElementById("manualDepartmentSelect");
    if (!select || isOfficer) return;
    try {
        const response = await fetch(`${API_BASE}/department/available-departments`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok) return;
        const departments = await response.json();
        select.innerHTML = '<option value="">Select department</option>' + departments.map(d =>
            `<option value="${d.department_id}">${escHtml(d.department_name)}${d.ai_supported ? "" : " (manual routing)"}</option>`
        ).join("");
    } catch (_) {}
}
loadTransferDepartments();


const manualRerouteBtn = document.getElementById("manualRerouteBtn");
if (manualRerouteBtn) manualRerouteBtn.addEventListener("click", async () => {
    const departmentId = Number(document.getElementById("manualDepartmentSelect").value);
    const reason = document.getElementById("manualRerouteReason").value.trim();
    const result = document.getElementById("recoveryResult");
    if (!departmentId) {
        result.textContent = "Select the correct destination department.";
        return;
    }
    if (!confirm("Transfer this complaint to the selected department? Any existing officer assignment in this department will be cleared.")) return;
    manualRerouteBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/manual-reroute`, {
            method: "PUT",
            headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            body: JSON.stringify({ department_id: departmentId, reason: reason || null })
        });
        const data = await response.json();
        result.textContent = apiMessage(data, "Unable to transfer complaint.");
        if (response.ok) {
            alert(`${data.message}. The complaint is now waiting for assignment in the new department.`);
            window.location.href = "department_dashboard.html";
        }
    } finally {
        manualRerouteBtn.disabled = false;
    }
});


// ===============================
// Department Head manual escalation
// ===============================
const manualEscalationBtn = document.getElementById("manualEscalationBtn");
if (manualEscalationBtn) {
    manualEscalationBtn.addEventListener("click", async () => {
        if (isOfficer) return;

        const level = Number(document.getElementById("manualEscalationLevel").value || 2);
        const reason = document.getElementById("manualEscalationReason").value.trim();
        const result = document.getElementById("manualEscalationResult");

        if (reason.length < 5) {
            result.textContent = "Enter a clear reason for escalation.";
            return;
        }

        manualEscalationBtn.disabled = true;
        result.textContent = "Escalating complaint...";

        try {
            const response = await fetch(`${API_BASE}/department/complaint/${complaintId}/escalate`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ level, reason })
            });

            const data = await response.json();
            result.textContent = data.message || data.detail || "Unable to escalate complaint.";

            if (response.ok) {
                document.getElementById("manualEscalationReason").value = "";
                loadComplaint();
            }
        } catch (error) {
            console.error(error);
            result.textContent = "Unable to escalate complaint right now.";
        } finally {
            manualEscalationBtn.disabled = false;
        }
    });
}

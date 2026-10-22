/* Pip: role-aware, local workflow guide for department staff. */
(() => {
  const role = String(localStorage.getItem("actual_role") || "manager").toLowerCase();
  if (!localStorage.getItem("access_token") || !["officer", "manager", "department_head"].includes(role)) return;

  const isOfficer = role === "officer";
  const isDashboard = location.pathname.toLowerCase().endsWith("department_dashboard.html");
  const isQueue = location.pathname.toLowerCase().endsWith("department_complaints.html");
  const isDetails = location.pathname.toLowerCase().endsWith("department_complaint_details.html");
  const flowKey = "civicflowPipGuideFlow";
  const pipPath = "images/pip-mascot.png?v=3";

  // The department dashboard previously contained an officer-only guide shell.
  // Replace that legacy shell so every staff page gets the same role-aware Pip.
  document.getElementById("officerGuide")?.remove();
  const root = document.createElement("div");
  root.className = "pip-guide";
  root.innerHTML = `
    <button class="pip-guide__launcher" type="button" aria-expanded="false" aria-controls="pipGuidePanel" aria-label="Ask Pip, the ${isOfficer ? "officer" : "department head"} guide">
      <img src="${pipPath}" alt="" aria-hidden="true"><span>Ask Pip</span>
    </button>
    <section class="pip-guide__panel" id="pipGuidePanel" aria-label="${isOfficer ? "Officer" : "Department Head"} workflow guide" aria-hidden="true">
      <header class="pip-guide__header"><div class="pip-guide__identity"><img src="${pipPath}" alt=""><div><strong>Pip · ${isOfficer ? "Officer Guide" : "Department Head Guide"}</strong><small>${isOfficer ? "Field work and complaint follow-up" : "Queue oversight and team coordination"}</small></div></div><button type="button" class="pip-guide__close" aria-label="Close Pip">×</button></header>
      <div class="pip-guide__messages" aria-live="polite" aria-relevant="additions"></div>
      <div class="pip-guide__suggestions"></div>
      <form class="pip-guide__form"><input class="pip-guide__input" autocomplete="off" aria-label="Ask Pip" placeholder="Ask where to find something…"><button class="pip-guide__mic" type="button" aria-label="Ask Pip by voice" title="Ask by voice" hidden><i class="fa-solid fa-microphone" aria-hidden="true"></i></button><button type="submit" aria-label="Send question"><i class="fa-solid fa-arrow-up" aria-hidden="true"></i></button></form>
    </section>
    <div class="pip-guide__tour" hidden role="status" aria-live="polite"><img src="${pipPath}" alt=""><div><strong class="pip-guide__tour-title">Pip’s pointer</strong><p class="pip-guide__tour-copy"></p><div class="pip-guide__tour-actions"><button type="button" class="pip-guide__tour-go"></button><button type="button" class="pip-guide__tour-close" aria-label="Close guidance">×</button></div></div></div>
    <div class="pip-guide__marker" aria-hidden="true"><img src="${pipPath}" alt=""></div>`;
  document.body.append(root);

  const launcher = root.querySelector(".pip-guide__launcher");
  const panel = root.querySelector(".pip-guide__panel");
  const messages = root.querySelector(".pip-guide__messages");
  const input = root.querySelector(".pip-guide__input");
  const suggestions = root.querySelector(".pip-guide__suggestions");
  const mic = root.querySelector(".pip-guide__mic");
  const tour = root.querySelector(".pip-guide__tour");
  const tourCopy = root.querySelector(".pip-guide__tour-copy");
  const tourGo = root.querySelector(".pip-guide__tour-go");
  const marker = root.querySelector(".pip-guide__marker");
  let recognition = null;
  let highlighted = null;
  let tourTarget = null;

  function pageName() {
    if (isDashboard) return "dashboard";
    if (isQueue) return "queue";
    if (isDetails) return "details";
    return "profile";
  }

  function addMessage(text, kind = "bot", action) {
    const row = document.createElement("article");
    row.className = `pip-guide__message pip-guide__message--${kind}`;
    if (kind === "bot") {
      const avatar = document.createElement("img");
      avatar.src = pipPath;
      avatar.alt = "Pip";
      row.append(avatar);
    }
    const body = document.createElement("div");
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    body.append(paragraph);
    if (action) {
      const button = document.createElement("button");
      button.className = "pip-guide__message-action";
      button.type = "button";
      button.textContent = action.label;
      button.addEventListener("click", action.run);
      body.append(button);
    }
    row.append(body);
    messages.append(row);
    messages.scrollTop = messages.scrollHeight;
  }

  function clearHighlight() {
    clearTourVisuals();
    sessionStorage.removeItem(flowKey);
  }

  function clearTourVisuals() {
    if (highlighted) highlighted.classList.remove("pip-guide-target");
    highlighted = null;
    tourTarget = null;
    tour.hidden = true;
    marker.classList.remove("is-visible");
  }

  function placeTour(el) {
    const rect = el.getBoundingClientRect();
    const markerX = Math.max(8, Math.min(innerWidth - 56, rect.left + rect.width / 2 - 24));
    const markerY = Math.max(8, Math.min(innerHeight - 56, rect.top - 50));
    marker.style.transform = `translate(${markerX}px, ${markerY}px)`;
    const width = Math.min(350, innerWidth - 28);
    const left = Math.max(14, Math.min(innerWidth - width - 14, rect.left + rect.width / 2 - width / 2));
    tour.style.left = `${left}px`;
    tour.style.top = "12px";
    const height = tour.offsetHeight;
    const below = rect.bottom + 14;
    const top = below + height <= innerHeight - 12 ? below : Math.max(12, rect.top - height - 14);
    tour.style.top = `${top}px`;
  }

  function guideTo(selector, copy, actionLabel, action) {
    const target = document.querySelector(selector);
    if (!target) {
      addMessage(copy);
      return false;
    }
    setOpen(false);
    if (highlighted) highlighted.classList.remove("pip-guide-target");
    highlighted = target;
    tourTarget = target;
    target.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center", inline: "nearest" });
    target.classList.add("pip-guide-target");
    tourCopy.textContent = copy;
    tourGo.textContent = actionLabel || "Done";
    tour.hidden = false;
    marker.classList.add("is-visible");
    tourGo.hidden = !action;
    tourGo.textContent = actionLabel || "";
    placeTour(target);
    requestAnimationFrame(() => { if (!tour.hidden && tourTarget === target) placeTour(target); });
    tourGo.onclick = action || null;
    return true;
  }

  function focusQueueFor(flow) {
    sessionStorage.setItem(flowKey, flow);
    const link = document.querySelector("#complaintsNavLabel")?.closest("li");
    if (isDashboard && link) {
      guideTo("#complaintsNavLabel", isOfficer ? "Your assigned work is listed here. Open it to choose a complaint." : "Open the department queue to review complaints and assign or reassign an officer.", "Open complaint queue", () => link.click());
      return;
    }
    if (isQueue) {
      waitForTarget(".view-btn", 0, flow);
      return;
    }
    if (isDetails) {
      showDetailsStep(flow);
      return;
    }
    addMessage("Open the department dashboard first, then choose the complaint queue from its left navigation.");
  }

  function waitForTarget(selector, attempt, flow) {
    const target = document.querySelector(selector);
    if (target) {
      const copy = isOfficer ? "Choose View on an assigned complaint. I’ll then point out its action and status controls." : "Choose View on the complaint you want to inspect. I’ll then point out its assignment and oversight controls.";
      guideTo(selector, copy);
      sessionStorage.setItem(flowKey, flow);
      return;
    }
    if (attempt < 20) setTimeout(() => waitForTarget(selector, attempt + 1, flow), 350);
    else addMessage("The complaint list is still loading or has no cases to open. Try again when a complaint appears.");
  }

  function showDetailsStep(flow) {
    if (flow === "assign" && !isOfficer) {
      guideTo("#officerAssignmentSection", "Review the current assignment and suitability explanation here. The Head can change an existing assignment with the Change assignment control.", "Done");
      sessionStorage.removeItem(flowKey);
    } else if (flow === "status" && isOfficer) {
      guideTo("#officerActionControls", "Record what you did in the action timeline first, then update the complaint status. Use In Progress only after work has started.", "Show status controls", () => {
        const status = document.querySelector("#statusUpdateSection");
        if (status) guideTo("#statusUpdateSection", "Choose the accurate status and add a short note if useful, then select Update Status.", "Done");
      });
      sessionStorage.removeItem(flowKey);
    } else if (flow === "resolve" && isOfficer) {
      guideTo("#resolutionProofSection", "Add a clear after-photo and resolution note before marking work complete. The citizen can confirm or reopen the resolution.", "Done");
      sessionStorage.removeItem(flowKey);
    } else if (flow === "delay" && isOfficer) {
      guideTo("#officerDelayForm", "Choose the real blocker, explain work already completed, and request the next time you can provide an update. The Department Head reviews the request.", "Done");
      sessionStorage.removeItem(flowKey);
    } else if (flow === "delay" && !isOfficer) {
      guideTo("#delayRequestList", "Review the officer’s stated blocker and requested follow-up time here. Approve or decline with a clear decision note.", "Done");
      sessionStorage.removeItem(flowKey);
    } else if (flow === "resolve" && !isOfficer) {
      addMessage("The assigned officer records resolution proof and marks the complaint resolved. You can review the proof and status here.");
      sessionStorage.removeItem(flowKey);
    } else if (flow === "queue") {
      addMessage(isOfficer ? "You are viewing a complaint from your assigned list. Ask me for help with actions, status or resolution proof." : "You are viewing a complaint in the department queue. Ask me for help with assignment, workload or SLA review.");
      sessionStorage.removeItem(flowKey);
    } else if (flow === "sla") {
      guideTo(".sla-panel", "The SLA panel shows the current estimate, deadline, time remaining and the estimate basis. It is a planning target, not a guarantee.", "Done");
      sessionStorage.removeItem(flowKey);
    } else {
      guideTo(isOfficer ? "#statusUpdateSection" : "#officerAssignmentSection", isOfficer ? "Update status after recording the work completed." : "Review this complaint’s assignment and operational details.", "Done");
    }
  }

  function waitForDetailsStep(flow, attempt = 0) {
    const title = document.querySelector("#title")?.textContent?.trim();
    if ((title && title !== "Loading...") || attempt >= 30) {
      showDetailsStep(flow);
      return;
    }
    setTimeout(() => waitForDetailsStep(flow, attempt + 1), 200);
  }

  function normalized(text) {
    return String(text || "").toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, " ").replace(/\s+/g, " ").trim();
  }

  function currentComplaintSummary() {
    const number = document.querySelector("#complaintId")?.textContent?.trim();
    const title = document.querySelector("#title")?.textContent?.trim();
    const status = document.querySelector("#status")?.textContent?.trim();
    return "You’re viewing complaint" + (number ? " #" + number : "") + (title ? ", “" + title + "”" : "") + (status ? " (status: " + status + ")" : "") + ". Ask about its assignment, status, SLA, delay request, resolution, or escalation.";
  }

  function answer(question) {
    const q = normalized(question);
    if (/escalat/.test(q) && !isOfficer) {
      if (isDetails) return { text: currentComplaintSummary().split(". Ask about")[0] + ". Use its Escalate Complaint section to enter a reason and select an escalation level.", run: () => guideTo("#manualEscalationSection", "This is the complaint currently open. Review its details, choose an escalation level, enter the reason, then select Escalate."), label: "Show escalation section" };
      if (isQueue) return { text: "The department complaints are already listed here. Choose View on the complaint you want to escalate; Pip will then point out that complaint’s escalation controls.", run: () => focusQueueFor("escalate"), label: "Point to View" };
      return { text: "Open the complaint you want to escalate. Pip will point out that complaint’s escalation controls.", run: () => focusQueueFor("escalate"), label: "Find a complaint" };
    }
    if (/complaint|queue|assigned|all reports|view cases|see cases/.test(q) && !/update|status|progress|assign|reassign|escalat|resolve|delay|sla|deadline|proof/.test(q)) {
      if (isDetails && !/queue|assigned|all reports|view cases|see cases/.test(q)) return { text: currentComplaintSummary(), label: "About this open complaint" };
      if (isQueue) return { text: isOfficer ? "Your assigned complaints are listed here. Choose View on the case you want to inspect." : "The department complaints are already listed here. Choose View on the row you want to inspect." };
      return { text: isOfficer ? "To see your work, open My Assigned Complaints, then choose View on a case." : "Open the Department Complaint Queue, then choose a complaint to inspect assignment and follow-up options.", run: () => focusQueueFor("queue"), label: "Show me the complaint queue" };
    }
    if (/update|status|progress|in progress/.test(q)) {
      if (!isOfficer) {
        if (isDetails) return { text: "No. Department Heads cannot change a complaint’s operational status to In Progress. The assigned officer records field actions and updates that status. You can review this complaint’s activity here.", run: () => guideTo("#actionTimeline", "This complaint is already open. Its assigned officer owns operational status updates; the action timeline shows recorded work and status changes."), label: "Review activity" };
        return { text: "No. Department Heads cannot change a complaint’s operational status to In Progress. The assigned officer records field actions and updates that status. You can review the case from the department queue.", run: () => focusQueueFor("assign"), label: "Go to the complaint queue" };
      }
      if (isDetails) return { text: "This complaint is open. Record the field action, then update its status from the officer controls.", run: () => showDetailsStep("status"), label: "Show status controls" };
      return { text: "I’ll guide you from your work list to the action notes and status controls.", run: () => focusQueueFor("status"), label: "Guide me through an update" };
    }
    if (/assign|reassign|officer recommendation/.test(q)) {
      if (isOfficer) return { text: "Assignment is managed by the Department Head. I can take you to your assigned work list.", run: () => focusQueueFor("queue"), label: "Open my assigned complaints" };
      if (isDetails) {
        const assignee = document.querySelector("#currentAssignee")?.textContent?.trim();
        const owner = assignee && !/^unassigned$/i.test(assignee) ? " Current assignment: " + assignee + "." : " This complaint is currently unassigned.";
        return { text: currentComplaintSummary().split(". Ask about")[0] + "." + owner + " Use Change assignment here to select a different officer.", run: () => guideTo("#officerAssignmentSection", "The current complaint’s assignment controls are here. Review the recommendation and existing assignee, then use Change assignment if a change is needed."), label: "Show assignment controls" };
      }
      if (isQueue) return { text: "Choose View beside the complaint you want to assign or reassign. I’ll point out its assignment controls after it opens.", run: () => focusQueueFor("assign"), label: "Point to View" };
      return { text: "Open a complaint from the department queue to review the recommended officer and assignment controls.", run: () => focusQueueFor("assign"), label: "Guide me to assignment" };
    }
    if (/escalat/.test(q) && !isOfficer) {
      if (isDetails) return { text: `Complaint #${document.querySelector("#complaintId")?.textContent?.trim() || "currently open"} is already open. Use its Escalate Complaint section to record a reason and select an escalation level.`, run: () => guideTo("#manualEscalationSection", "This is the complaint currently open. Review its details, choose an escalation level, enter the reason, then select Escalate."), label: "Show escalation section" };
      return { text: "Open the complaint you want to escalate. Pip will point out that complaint’s escalation controls.", run: () => focusQueueFor("escalate"), label: "Find a complaint" };
    }
    if (/delay|late|more time|blocker|extension/.test(q)) {
      if (!isOfficer) return { text: isDetails ? "For this complaint, review the officer’s stated blocker and requested follow-up time below. The Head records the decision; Pip does not approve deadline changes." : isQueue ? "Choose View on the complaint whose delay request you want to review. The Head records the decision; Pip does not approve deadline changes." : "Officers can submit a blocker and requested follow-up time from a complaint. The Head reviews it; Pip does not approve deadline changes.", run: () => focusQueueFor("delay"), label: isDetails ? "Show delay request" : isQueue ? "Point to View" : "Go to the complaint queue" };
      if (isDetails) return { text: "Use the delay request section to explain the blocker and the next update time you can commit to.", run: () => showDetailsStep("delay"), label: "Show the delay request" };
      return { text: "Open the assigned complaint first. I’ll point out the follow-up request form there.", run: () => focusQueueFor("delay"), label: "Find a complaint" };
    }
    if (/resolve|resolution|proof|close case/.test(q)) {
      if (!isOfficer) return { text: isDetails ? "For this open complaint, the assigned officer records resolution proof and marks the work complete. You can review the status and follow up with the officer from this page." : "The assigned officer records resolution proof and marks work complete. The Head can review progress and follow up.", run: () => focusQueueFor("resolve"), label: isDetails ? "Review this complaint" : "Review a complaint" };
      if (isDetails) return { text: "Before resolving, document the completed work and attach clear evidence when available.", run: () => showDetailsStep("resolve"), label: "Show resolution proof" };
      return { text: "Open an assigned complaint and Pip will point out the resolution proof section.", run: () => focusQueueFor("resolve"), label: "Find a complaint" };
    }
    if (isDetails && /complaint|case|report|this/.test(q) && !/queue|assigned/.test(q)) {
      const number = document.querySelector("#complaintId")?.textContent?.trim();
      const title = document.querySelector("#title")?.textContent?.trim();
      const status = document.querySelector("#status")?.textContent?.trim();
      return { text: `You’re viewing complaint${number ? ` #${number}` : ""}${title ? `, “${title}”` : ""}${status ? ` (status: ${status})` : ""}. Ask about its assignment, status, SLA, delay request, resolution, or escalation.`, label: "About this open complaint" };
    }
    if (/sla|deadline|breach|time remaining/.test(q)) {
      if (isDetails) return { text: "The SLA estimate and its basis are shown on this complaint page.", run: () => showDetailsStep("sla"), label: "Show the SLA panel" };
      if (isDashboard && !isOfficer) return { text: "The Head’s dashboard includes the SLA risk and escalation queue.", run: () => guideTo("#escalationPanel", "Review cases at risk or overdue here, then open a case for its detailed SLA history.", "Done"), label: "Show SLA risks" };
      if (isQueue) return { text: "Choose View on the complaint whose deadline you want to review. Its detail page shows the SLA estimate and time remaining.", run: () => focusQueueFor("sla"), label: "Point to View" };
      return { text: "Open a complaint to see its current estimate, deadline and remaining time.", run: () => focusQueueFor("sla"), label: "Open a complaint" };
    }
    if (/performance|workload|officer metrics|team/.test(q) && !isOfficer) {
      if (isDashboard) return { text: "Officer posting, current workload and historical performance are shown in the team section.", run: () => guideTo("#officerPerformanceBody", "Compare posting, active load, SLA compliance and history together. The suitability score is only a routing aid.", "Done"), label: "Show team performance" };
      return { text: "Open the Department Head dashboard to review the officer team and workload table.", run: () => { location.href = "department_dashboard.html#officerPerformanceBody"; }, label: "Open dashboard" };
    }
    if (/incident|map|cluster/.test(q) && !isOfficer && isDashboard) {
      return { text: "The incident map and early-warning cluster panel are on the Department Head dashboard.", run: () => guideTo("#departmentIncidentMap", "Use the map to inspect mapped complaints, then review the incident alert information above or below it.", "Done"), label: "Show incident map" };
    }
    if (/notification|bell/.test(q)) return { text: "Use the notification bell in the top bar for assignment, SLA and citizen follow-up alerts.", run: () => isDashboard ? guideTo("#departmentNotificationBtn", "Open the bell to review unread work notifications.", "Done") : addMessage("Return to the dashboard and use the bell in the top bar."), label: "Show notifications" };
    if (/profile|password|account/.test(q)) {
      if (isOfficer) return { text: "Your account details are in Account / Password. Open it from the dashboard navigation.", run: () => isDashboard ? guideTo("#profileNavLabel", "Open Account / Password to review your account details.", "Open account", () => document.querySelector("#profileNavLabel")?.closest("li")?.click()) : (location.href = "department_profile.html"), label: "Open account" };
      return { text: "Department identity and contact settings are available in Department Profile.", run: () => location.href = "department_profile.html", label: "Open department profile" };
    }
    return { text: isOfficer ? "I can guide you to assigned complaints, action notes, status updates, resolution proof, delay requests and SLA information." : "I can guide you through the complaint queue, officer recommendations, workload, SLA risks, incidents and department settings.", label: "What can you help with?" };
  }

  function ask(question) {
    const clean = String(question || "").trim();
    if (!clean) return;
    addMessage(clean, "user");
    const result = answer(clean);
    addMessage(result.text, "bot", result.run ? { label: result.label, run: result.run } : null);
  }

  const roleWelcome = isOfficer
    ? "I can show you where to open assigned complaints, record field actions, update status, request follow-up time and add resolution proof."
    : "I can show you how to review the department queue, check recommendations, assign or reassign officers, and review SLA risks.";
  addMessage(roleWelcome);

  const chips = isOfficer
    ? [["Where are my complaints?", "Find my complaints"], ["How do I update status?", "Update status"], ["How do I request more time?", "Request follow-up time"]]
    : [["How do I review assignments?", "Review assignments"], ["Where is officer performance?", "Officer workload"], ["Where are SLA risks?", "SLA risks"]];
  chips.forEach(([text, question]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.addEventListener("click", () => ask(question));
    suggestions.append(button);
  });

  function setOpen(open) {
    panel.classList.toggle("is-open", open);
    panel.setAttribute("aria-hidden", String(!open));
    launcher.setAttribute("aria-expanded", String(open));
    if (open) input.focus();
  }
  launcher.addEventListener("click", () => setOpen(!panel.classList.contains("is-open")));
  root.querySelector(".pip-guide__close").addEventListener("click", () => setOpen(false));
  root.querySelector(".pip-guide__tour-close").addEventListener("click", clearHighlight);
  root.querySelector(".pip-guide__form").addEventListener("submit", event => {
    event.preventDefault();
    ask(input.value);
    input.value = "";
  });
  if (window.CivicFlowVoice?.supported) {
    mic.hidden = false;
    mic.addEventListener("click", () => {
      if (recognition) {
        recognition.stop();
        return;
      }
      recognition = window.CivicFlowVoice.createRecognition({ continuous: false, interimResults: false, lang: "en-IN" });
      if (!recognition) return;
      mic.classList.add("is-listening");
      mic.setAttribute("aria-label", "Stop listening to Pip");
      addMessage("I’m listening. Ask your question in English.");
      recognition.onresult = event => {
        const transcript = event.results?.[0]?.[0]?.transcript || "";
        if (transcript) ask(transcript);
      };
      recognition.onerror = () => addMessage("Voice input stopped. You can type your question instead.");
      recognition.onend = () => {
        recognition = null;
        mic.classList.remove("is-listening");
        mic.setAttribute("aria-label", "Ask Pip by voice");
      };
      try { recognition.start(); }
      catch (_) { recognition = null; mic.classList.remove("is-listening"); mic.setAttribute("aria-label", "Ask Pip by voice"); }
    });
  }
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      setOpen(false);
      clearHighlight();
    }
  });
  window.addEventListener("resize", () => {
    if (!tour.hidden && tourTarget?.isConnected) {
      placeTour(tourTarget);
    }
  }, { passive: true });
  let repositionFrame = 0;
  window.addEventListener("scroll", () => {
    if (!tour.hidden && tourTarget?.isConnected && !repositionFrame) {
      repositionFrame = requestAnimationFrame(() => {
        repositionFrame = 0;
        if (!tour.hidden && tourTarget?.isConnected) placeTour(tourTarget);
      });
    }
  }, { passive: true });
  window.addEventListener("pagehide", clearTourVisuals);
  window.addEventListener("pageshow", event => {
    if (event.persisted) clearHighlight();
  });

  const pendingFlow = sessionStorage.getItem(flowKey);
  if (pendingFlow && isQueue) setTimeout(() => waitForTarget(".view-btn", 0, pendingFlow), 400);
  if (pendingFlow && isDetails) setTimeout(() => waitForDetailsStep(pendingFlow), 150);
  if (isDashboard && location.hash === "#officerPerformanceBody" && !isOfficer) {
    setTimeout(() => guideTo("#officerPerformanceBody", "Compare posting, active load, SLA compliance and history together.", "Done"), 350);
  }
})();

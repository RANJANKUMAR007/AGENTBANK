// AgentBank Front-End Controller: Multi-Customer Conversations & Live Orchestration Trace
document.addEventListener("DOMContentLoaded", () => {
  const customerSelect = document.getElementById("customerSelect");
  const customerTabsBar = document.getElementById("customerTabsBar");
  const btnClearChat = document.getElementById("btnClearChat");
  const messagesContainer = document.getElementById("messagesContainer");
  const chatForm = document.getElementById("chatForm");
  const userInput = document.getElementById("userInput");
  const btnSend = document.getElementById("btnSend");
  const traceContent = document.getElementById("traceContent");
  const traceIdBadge = document.getElementById("traceIdBadge");
  const emptyTrace = document.getElementById("emptyTrace");
  const systemStatus = document.getElementById("systemStatus");

  const btnGenerateCustomer = document.getElementById("btnGenerateCustomer");
  const lookupIdInput = document.getElementById("lookupIdInput");
  const btnLookupCustomer = document.getElementById("btnLookupCustomer");
  const chipName = document.getElementById("chipName");
  const chipScore = document.getElementById("chipScore");
  const chipKyc = document.getElementById("chipKyc");

  // Stable Browser Session ID (persisted across page reloads)
  let browserSessionId = localStorage.getItem("agentbank_browser_session_id");
  if (!browserSessionId) {
    browserSessionId = `browser_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    localStorage.setItem("agentbank_browser_session_id", browserSessionId);
  }

  // Active Customer ID
  let currentCustomerId = localStorage.getItem("agentbank_active_customer") || "CUST_001";
  let customersCache = [];

  // Local Storage Chat History Store keyed by customer_id
  // Structure: { [custId]: { items: [...], traceData: {...}, unreadCount: 0 } }
  let customerStore = {};
  try {
    const raw = localStorage.getItem("agentbank_customer_chats_v2");
    if (raw) {
      customerStore = JSON.parse(raw);
    }
  } catch (e) {
    console.error("Failed to parse local chat history:", e);
    customerStore = {};
  }

  function saveStore() {
    try {
      localStorage.setItem("agentbank_customer_chats_v2", JSON.stringify(customerStore));
      localStorage.setItem("agentbank_active_customer", currentCustomerId);
    } catch (e) {
      console.error("Failed to save customer chats to localStorage:", e);
    }
  }

  function getCustomerState(custId) {
    if (!customerStore[custId]) {
      customerStore[custId] = {
        items: [],
        traceData: null,
        unreadCount: 0
      };
    }
    return customerStore[custId];
  }

  function getCustomerName(custId) {
    const found = customersCache.find((c) => c.customer_id === custId);
    if (found) return found.name;
    if (custId === "CUST_001") return "Priya Sharma";
    if (custId === "CUST_002") return "Arjun Patel";
    if (custId === "CUST_003") return "Meera Iyer";
    return custId;
  }

  function getCustomerFirstName(custId) {
    const full = getCustomerName(custId);
    return full.split(" ")[0] || full;
  }

  // Helper: Escape HTML to prevent XSS
  function escapeHTML(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Helper: Convert markdown formatting (**bold**, bullet lists, linebreaks) to HTML
  function formatMarkdown(text) {
    if (!text) return "";
    let safe = escapeHTML(text);

    // Convert **bold** to <strong>bold</strong>
    safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Convert bullet list items (- item or * item)
    const lines = safe.split("\n");
    let inList = false;
    let formattedLines = [];

    for (let line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        if (!inList) {
          inList = true;
          formattedLines.push("<ul style='margin: 6px 0 6px 18px; padding-left: 0;'>");
        }
        formattedLines.push(`<li>${trimmed.substring(2)}</li>`);
      } else {
        if (inList) {
          inList = false;
          formattedLines.push("</ul>");
        }
        formattedLines.push(line);
      }
    }
    if (inList) {
      formattedLines.push("</ul>");
    }

    return formattedLines.join("<br/>").replace(/<\/ul><br\/>/g, "</ul>");
  }

  // Render Customer Tabs & Sync Dropdown
  function renderCustomerTabs() {
    if (!customerTabsBar) return;
    customerTabsBar.innerHTML = "";

    customersCache.forEach((c) => {
      const custId = c.customer_id;
      const state = getCustomerState(custId);
      const isActive = custId === currentCustomerId;

      const tab = document.createElement("button");
      tab.className = `customer-tab ${isActive ? "active" : ""}`;
      tab.setAttribute("data-cust-id", custId);
      tab.title = `Switch conversation to ${c.name} (${custId})`;

      const initial = (c.name || "C").trim().charAt(0).toUpperCase();
      let badgeHtml = "";
      if (!isActive && state.unreadCount > 0) {
        badgeHtml = `<span class="tab-badge">${state.unreadCount}</span><span class="tab-unread-dot"></span>`;
      }

      tab.innerHTML = `
        <span class="tab-avatar">${initial}</span>
        <span class="tab-name">${escapeHTML(c.name)}</span>
        ${badgeHtml}
      `;

      tab.addEventListener("click", () => {
        if (currentCustomerId !== custId) {
          switchCustomer(custId);
        }
      });

      customerTabsBar.appendChild(tab);
    });

    // Update Dropdown options to show unread indicators
    customerSelect.innerHTML = "";
    customersCache.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.customer_id;
      const state = getCustomerState(c.customer_id);
      let suffix = "";
      if (c.anomaly_injected) suffix += " ⚠️ Anomaly";
      if (c.customer_id !== currentCustomerId && state.unreadCount > 0) {
        suffix += ` (${state.unreadCount} unread)`;
      }
      opt.innerText = `${c.name} (${c.customer_id})${suffix}`;
      customerSelect.appendChild(opt);
    });
    customerSelect.value = currentCustomerId;
  }

  // Refresh customer dropdown from /api/customers
  async function loadCustomersList(selectIdToPick = null) {
    try {
      const res = await fetch("/api/customers");
      if (!res.ok) return;
      const data = await res.json();
      customersCache = data.customers || [];

      if (selectIdToPick) {
        currentCustomerId = selectIdToPick;
      } else if (!customersCache.some((c) => c.customer_id === currentCustomerId)) {
        currentCustomerId = customersCache[0]?.customer_id || "CUST_001";
      }

      renderCustomerTabs();
      updateActiveProfileChip();
      renderActiveCustomerChat();
    } catch (e) {
      console.error("Failed to load customer list:", e);
    }
  }

  // Update profile badge chip
  function updateActiveProfileChip() {
    const active = customersCache.find((c) => c.customer_id === currentCustomerId);
    if (active) {
      chipName.innerText = active.name;
      chipScore.innerText = `CIBIL: ${active.credit_score || "N/A"}`;
      chipKyc.innerText = `KYC: ${active.kyc_status || "VERIFIED"}`;

      if (active.credit_score >= 750) {
        chipScore.className = "chip-badge badge-success";
      } else if (active.credit_score >= 650) {
        chipScore.className = "chip-badge badge-info";
      } else {
        chipScore.className = "chip-badge badge-danger";
      }
    } else {
      chipName.innerText = currentCustomerId;
      chipScore.innerText = "CIBIL: --";
      chipKyc.innerText = "KYC: --";
    }
  }

  // Render the active customer's conversation and trace from local state
  function renderActiveCustomerChat() {
    messagesContainer.innerHTML = "";
    const state = getCustomerState(currentCustomerId);

    // If active customer has no history yet, display a fresh welcome message
    if (!state.items || state.items.length === 0) {
      const firstName = getCustomerFirstName(currentCustomerId);
      const welcomeText = `Hi ${firstName}, how can I help you today?`;
      state.items = [
        {
          type: "message",
          role: "assistant",
          text: welcomeText,
          timestamp: Date.now()
        }
      ];
      saveStore();
    }

    // Mark unread as 0 for active customer
    state.unreadCount = 0;
    saveStore();

    // Re-render items
    state.items.forEach((item) => {
      if (item.type === "message") {
        appendMessageElement(item.role, item.text);
      } else if (item.type === "approval") {
        appendApprovalCardElement(item.action);
      }
    });

    // Re-render active customer's trace
    if (state.traceData) {
      renderTrace(state.traceData);
    } else {
      resetTrace();
    }

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    renderCustomerTabs();
  }

  // Switch customer handler: saves current chat, loads and renders selected customer's chat and trace
  function switchCustomer(newId) {
    if (!newId || newId === currentCustomerId) return;
    currentCustomerId = newId;
    localStorage.setItem("agentbank_active_customer", currentCustomerId);

    updateActiveProfileChip();
    renderActiveCustomerChat();
  }

  customerSelect.addEventListener("change", (e) => {
    switchCustomer(e.target.value);
  });

  // "Clear this chat" Button handler
  btnClearChat.addEventListener("click", async () => {
    const custName = getCustomerName(currentCustomerId);
    if (!confirm(`Are you sure you want to clear the conversation history for ${custName}?`)) {
      return;
    }

    // Reset customer state in store
    customerStore[currentCustomerId] = {
      items: [],
      traceData: null,
      unreadCount: 0
    };
    saveStore();

    // Inform server to clear conversation memory
    try {
      await fetch("/api/chat/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: currentCustomerId,
          session_id: browserSessionId
        })
      });
    } catch (e) {
      console.warn("Could not notify server of chat clear:", e);
    }

    // Re-render fresh welcome message and reset trace
    renderActiveCustomerChat();
  });

  // Generate new customer button
  btnGenerateCustomer.addEventListener("click", async () => {
    btnGenerateCustomer.disabled = true;
    btnGenerateCustomer.innerText = "Generating...";
    try {
      const res = await fetch("/api/customers/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      if (!res.ok) throw new Error("Generation failed");
      const data = await res.json();
      const newCust = data.customer;

      await loadCustomersList(newCust.customer_id);
    } catch (err) {
      alert("Failed to generate synthetic customer: " + err.message);
    } finally {
      btnGenerateCustomer.disabled = false;
      btnGenerateCustomer.innerText = "+ Generate Customer";
    }
  });

  // Look up customer by ID
  btnLookupCustomer.addEventListener("click", () => {
    const queryId = lookupIdInput.value.trim().toUpperCase();
    if (!queryId) return;

    const matched = customersCache.find((c) => c.customer_id.toUpperCase() === queryId);
    if (matched) {
      switchCustomer(matched.customer_id);
      lookupIdInput.value = "";
    } else {
      alert(`Customer ID '${queryId}' not found in registry.`);
    }
  });

  lookupIdInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      btnLookupCustomer.click();
    }
  });

  // Prompt chip clicks
  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      userInput.value = chip.getAttribute("data-prompt");
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  // Form submit
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;

    const targetCustId = currentCustomerId;
    const state = getCustomerState(targetCustId);

    // Append to local store & DOM
    state.items.push({
      type: "message",
      role: "user",
      text: text,
      timestamp: Date.now()
    });
    saveStore();
    appendMessageElement("user", text);

    userInput.value = "";
    userInput.disabled = true;
    btnSend.disabled = true;
    systemStatus.innerText = "Processing request...";

    // Show temporary typing row
    const typingRow = appendTypingIndicator();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          customer_id: targetCustId,
          session_id: browserSessionId
        })
      });

      typingRow.remove();

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();

      // Save assistant message to target customer's history
      state.items.push({
        type: "message",
        role: "assistant",
        text: data.response,
        timestamp: Date.now()
      });

      // Attach pending approval cards to this customer's chat
      if (data.pending_actions && data.pending_actions.length > 0) {
        data.pending_actions.forEach((act) => {
          state.items.push({
            type: "approval",
            action: {
              ...act,
              status: "pending"
            }
          });
        });
      }

      // Store latest trace data for this customer
      state.traceData = data;

      // If user switched away while processing, increment unreadCount
      if (currentCustomerId !== targetCustId) {
        state.unreadCount = (state.unreadCount || 0) + 1;
        saveStore();
        renderCustomerTabs();
      } else {
        // Still on active customer: render directly to DOM
        saveStore();
        appendMessageElement("assistant", data.response);
        if (data.pending_actions && data.pending_actions.length > 0) {
          data.pending_actions.forEach((act) => {
            appendApprovalCardElement({
              ...act,
              status: "pending"
            });
          });
        }
        renderTrace(data);
      }
    } catch (err) {
      typingRow.remove();
      const errText = `Service Error: Unable to process request (${err.message}). Please check backend status.`;
      state.items.push({
        type: "message",
        role: "assistant",
        text: errText,
        timestamp: Date.now()
      });
      saveStore();
      if (currentCustomerId === targetCustId) {
        appendMessageElement("assistant", errText);
      }
    } finally {
      userInput.disabled = false;
      btnSend.disabled = false;
      userInput.focus();
      systemStatus.innerText = "Ready (Orchestrator Active)";
    }
  });

  function appendMessageElement(role, text) {
    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const avatar = document.createElement("div");
    avatar.className = `avatar ${role === "user" ? "user-avatar" : "bot-avatar"}`;
    avatar.innerText = role === "user" ? "YOU" : "AB";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = formatMarkdown(text);

    row.appendChild(avatar);
    row.appendChild(bubble);
    messagesContainer.appendChild(row);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return row;
  }

  function appendTypingIndicator() {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.innerHTML = `
      <div class="avatar bot-avatar">AB</div>
      <div class="bubble" style="color: #64748b; font-style: italic;">
        Consulting supervisor and specialist agents...
      </div>
    `;
    messagesContainer.appendChild(row);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return row;
  }

  function appendApprovalCardElement(action) {
    const card = document.createElement("div");
    card.className = "approval-card";
    const isResolved = action.status === "approved" || action.status === "rejected";

    let actionsHtml = "";
    if (isResolved) {
      const isApproved = action.status === "approved";
      actionsHtml = `
        <span class="badge ${isApproved ? 'badge-success' : 'badge-warning'}">
          ${isApproved ? 'AUTHORIZED' : 'CANCELLED'}
        </span>
        <span style="font-size: 12px; color: #475569; margin-left: 8px;">${escapeHTML(action.resultMessage || (isApproved ? 'Action executed' : 'Cancelled by user'))}</span>
      `;
    } else {
      actionsHtml = `
        <button class="btn-approve" onclick="handleHITLApproval('${action.action_id}', true)">Approve & Execute</button>
        <button class="btn-reject" onclick="handleHITLApproval('${action.action_id}', false)">Reject / Cancel</button>
      `;
    }

    card.innerHTML = `
      <div class="approval-title">
        <span>⚠️ Security Action Authorization Required</span>
      </div>
      <div class="approval-text">
        <strong>${escapeHTML(action.action_type)}</strong>: ${escapeHTML(action.message || action.reason || "")}
      </div>
      <div class="approval-actions" id="actions_${action.action_id}">
        ${actionsHtml}
      </div>
    `;
    messagesContainer.appendChild(card);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // Global window handler for HITL buttons
  window.handleHITLApproval = async function (actionId, approved) {
    const container = document.getElementById(`actions_${actionId}`);
    if (container) {
      container.innerHTML = `<span style="font-size: 12px; color: #64748b;">Submitting authorization...</span>`;
    }

    try {
      const res = await fetch("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_id: actionId,
          approved: approved,
          customer_id: currentCustomerId
        })
      });
      const resData = await res.json();

      // Update state in active customer's items
      const state = getCustomerState(currentCustomerId);
      const targetItem = state.items.find(
        (it) => it.type === "approval" && it.action && it.action.action_id === actionId
      );
      if (targetItem) {
        targetItem.action.status = approved ? "approved" : "rejected";
        targetItem.action.resultMessage = resData.message;
        saveStore();
      }

      if (container) {
        container.innerHTML = `
          <span class="badge ${approved ? 'badge-success' : 'badge-warning'}">
            ${approved ? 'AUTHORIZED' : 'CANCELLED'}
          </span>
          <span style="font-size: 12px; color: #475569; margin-left: 8px;">${escapeHTML(resData.message)}</span>
        `;
      }
    } catch (e) {
      if (container) {
        container.innerHTML = `<span style="color: #dc2626; font-size: 12px;">Failed to submit: ${escapeHTML(e.message)}</span>`;
      }
    }
  };

  function resetTrace() {
    traceContent.innerHTML = "";
    if (emptyTrace) {
      traceContent.appendChild(emptyTrace);
    }
    traceIdBadge.innerText = "Trace: Idle";
  }

  function renderTrace(data) {
    traceContent.innerHTML = "";
    const trace = data.trace || {};
    const guardrail = data.guardrail || {};

    traceIdBadge.innerText = `Trace: ${data.trace_id || "N/A"}`;

    // 1. Guardrail Box
    const guardDiv = document.createElement("div");
    guardDiv.className = `trace-step ${guardrail.passed === false ? 'blocked' : 'completed'}`;
    guardDiv.innerHTML = `
      <div class="step-badge">${guardrail.passed === false ? 'SAFETY BLOCKED' : 'SAFETY PASSED'}</div>
      <div class="step-title">AI Gateway Guardrails</div>
      <div class="step-detail">
        Rules Evaluated: <code>${(guardrail.applied_rules || []).join(", ") || "Domain, Cross-Customer, Injection"}</code>
        ${guardrail.passed === false ? `<div style="color: #dc2626; margin-top: 4px; font-weight: 600;">Violation: ${guardrail.refusal_reason}</div>` : ""}
      </div>
    `;
    traceContent.appendChild(guardDiv);

    // 2. Supervisor Route & Intent Box
    const supDiv = document.createElement("div");
    supDiv.className = "trace-step completed";
    const routeName = trace.route || "specialist";
    const isGeneral = routeName.includes("general");
    supDiv.innerHTML = `
      <div class="step-badge" style="background: ${isGeneral ? '#0284c7' : '#1e3a8a'};">
        ${isGeneral ? 'SUPERVISOR DIRECT' : 'SUPERVISOR ORCHESTRATION'}
      </div>
      <div class="step-title">Supervisor Routing Decision</div>
      <div class="step-detail">
        <strong>Route:</strong> <code>${escapeHTML(routeName)}</code><br/>
        <strong>Intent:</strong> <code>${escapeHTML(trace.intent || 'GENERAL_ASSISTANCE')}</code><br/>
        <div style="margin-top: 4px;"><strong>Reasoning:</strong> ${escapeHTML(trace.reasoning || 'Evaluated user message and determined execution path.')}</div>
      </div>
    `;
    traceContent.appendChild(supDiv);

    // 3. Specialist Agent Execution Cards
    if (trace.tool_calls && trace.tool_calls.length > 0) {
      trace.tool_calls.forEach((tc) => {
        const tcDiv = document.createElement("div");
        tcDiv.className = "trace-step completed";
        tcDiv.innerHTML = `
          <div class="step-badge" style="background: #059669;">TOOL EXECUTION</div>
          <div class="step-title">${escapeHTML(tc.agent || 'Specialist Agent')} &rarr; <code>${escapeHTML(tc.tool)}</code></div>
          <div class="step-detail">
            <strong>Arguments:</strong> <pre style="font-size: 11px; background: #f1f5f9; padding: 4px; border-radius: 4px; margin: 4px 0;">${escapeHTML(JSON.stringify(tc.arguments, null, 2))}</pre>
            <strong>Status:</strong> <span class="badge badge-success">${escapeHTML(tc.status || 'success')}</span>
          </div>
        `;
        traceContent.appendChild(tcDiv);
      });
    }

    // 4. Metrics / Summary Bar
    const summaryDiv = document.createElement("div");
    summaryDiv.className = "trace-step completed";
    summaryDiv.innerHTML = `
      <div class="step-badge" style="background: #475569;">METRICS</div>
      <div class="step-title">Execution Summary</div>
      <div class="step-detail" style="font-size: 12px; color: #475569;">
        Total Agents Executed: <strong>${(trace.agents_executed || []).length}</strong> &bull;
        Tool Calls: <strong>${(trace.tool_calls || []).length}</strong> &bull;
        Duration: <strong>${trace.duration_ms || 0} ms</strong>
      </div>
    `;
    traceContent.appendChild(summaryDiv);
  }

  // Initial load
  loadCustomersList();
});

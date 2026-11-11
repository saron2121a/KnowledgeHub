const $ = (id) => document.getElementById(id);

let history = [];
let isAsking = false;

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));

  if (!r.ok) {
    throw new Error(data.detail || r.statusText);
  }

  return data;
}

function clearConversation(message = "New chat.") {
  history = [];
  $("chat").replaceChildren();
  $("metrics").textContent = message;
  $("compare-out").textContent = "";
}

async function loadDocs() {
  const docs = await api("/api/documents");
  const ul = $("docs");
  const scope = $("scope");
  const previousScope = scope.value;

  ul.replaceChildren();
  scope.replaceChildren();

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All documents";
  scope.append(allOption);

  docs.forEach((d) => {
    // Document list
    const li = document.createElement("li");
    li.textContent = `${d.name} — ${d.chunks} chunks (${d.status}) `;

    const b = document.createElement("button");
    b.textContent = "Delete";

    b.onclick = async () => {
      try {
        await api("/api/documents/" + encodeURIComponent(d.name), {
          method: "DELETE",
        });

        await loadDocs();
      } catch (e) {
        $("upload-msg").textContent = "Error: " + e.message;
      }
    };

    li.append(b);
    ul.append(li);

    // Document scope dropdown
    const option = document.createElement("option");
    option.value = d.name;
    option.textContent = d.name;
    scope.append(option);
  });

  // Keep the previous selection if that document still exists.
  const stillExists = docs.some((d) => d.name === previousScope);
  scope.value = stillExists ? previousScope : "";

  // If the selected document was deleted, reset the conversation.
  if (scope.value !== previousScope) {
    clearConversation(
      "Selected document is no longer available. Switched to all documents.",
    );
  }
}

$("upload").onclick = async () => {
  const f = $("file").files[0];

  if (!f) return;

  const fd = new FormData();
  fd.append("file", f);

  try {
    const d = await api("/api/documents", {
      method: "POST",
      body: fd,
    });

    $("upload-msg").textContent = `Indexed ${d.name} (${d.chunks} chunks)`;

    await loadDocs();
  } catch (e) {
    $("upload-msg").textContent = "Error: " + e.message;
  }
};

function addMsg(role, text, sources) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;

  if (sources && sources.length) {
    const s = document.createElement("div");
    s.className = "src";
    s.textContent =
      "Sources: " +
      sources.map((x) => `${x.source} (chunk ${x.chunk})`).join(", ");

    div.append(s);
  }

  $("chat").append(div);
  $("chat").scrollTop = $("chat").scrollHeight;
}

function showMetrics(d) {
  const m = $("metrics");
  m.replaceChildren();

  const badge = document.createElement("span");
  badge.className = "badge " + d.cache;
  badge.textContent = d.cache;

  const t = d.timings || {};

  const parts = [
    `${d.ms} ms`,
    d.from === "redis" ? "served from Redis" : "newly generated",
    `retrieved: ${d.retrieved}`,
    `rerank: ${d.rerank_status} (${d.reranked} passages)`,
  ];

  if (d.reason) {
    parts.push(d.reason);
  }

  if (t.retrieval_ms !== undefined) {
    parts.push(
      `retrieval ${t.retrieval_ms} ms / rerank ${t.rerank_ms} ms / generation ${t.generation_ms} ms`,
    );
  }

  m.append(badge, " " + parts.join(" · "));
}

async function ask() {
  if (isAsking) return;

  const q = $("question").value.trim();

  if (!q) return;

  isAsking = true;

  const askButton = $("ask");
  const compareButton = $("compare");
  const originalAskText = askButton.textContent;

  askButton.disabled = true;
  compareButton.disabled = true;
  askButton.textContent = "Processing...";

  $("question").value = "";
  addMsg("user", q);

  try {
    const d = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: q,
        history,
        document: $("scope").value || null,
      }),
    });

    addMsg("bot", d.answer, d.sources);
    showMetrics(d);

    history.push(
      { role: "user", content: q },
      { role: "assistant", content: d.answer },
    );
  } catch (e) {
    addMsg("bot", "Error: " + e.message);
  } finally {
    isAsking = false;
    askButton.disabled = false;
    compareButton.disabled = false;
    askButton.textContent = originalAskText;
  }
}

$("scope").addEventListener("change", () => {
  const selected = $("scope").value;

  const message = selected
    ? `Switched to ${selected}. Conversation history cleared.`
    : "Switched to all documents. Conversation history cleared.";

  clearConversation(message);
});

$("newchat").onclick = () => {
  clearConversation("New chat. The next question can use the cache.");
};

$("ask").onclick = ask;

$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    ask();
  }
});

$("compare").onclick = async () => {
  const q = $("question").value.trim();

  if (!q) return;

  try {
    const params = new URLSearchParams({ q });
    const document = $("scope").value;

    if (document) {
      params.set("document", document);
    }

    const d = await api("/api/compare?" + params.toString());

    $("compare-out").textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    $("compare-out").textContent = "Error: " + e.message;
  }
};

loadDocs().catch((e) => {
  $("upload-msg").textContent = "Could not load documents: " + e.message;
});

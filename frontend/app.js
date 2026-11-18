const authView = document.querySelector("#authView");
const appView = document.querySelector("#appView");
const authForm = document.querySelector("#authForm");
const quizForm = document.querySelector("#quizForm");
let authMode = "login";
let accountQuestionIds = [];

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}

async function refreshSession() {
  const status = await api("/api/session");
  authView.classList.toggle("hidden", status.authenticated);
  appView.classList.toggle("hidden", !status.authenticated);
  document.querySelector("#logoutButton").classList.toggle("hidden", !status.authenticated);
  if (status.authenticated) loadPasswords();
}

document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", async () => {
    authMode = tab.dataset.tab;
    document.querySelectorAll(".tab").forEach(item => item.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector("#authPassword").autocomplete =
      authMode === "login" ? "current-password" : "new-password";
    document.querySelector("#profileFields").classList.toggle("hidden", authMode !== "register");
    document.querySelector("#accountQuiz").classList.toggle("hidden", authMode !== "register");
    if (authMode === "register") await loadAccountQuestions();
  });
});

async function loadAccountQuestions() {
  const quiz = document.querySelector("#accountQuiz");
  const heading = quiz.querySelector("h2");
  try {
    const data = await api("/api/questions?kind=account");
    quiz.innerHTML = "";
    quiz.appendChild(heading);
    accountQuestionIds = [];
    data.questions.forEach((question, index) => {
      accountQuestionIds.push(String(question.id));
      const fieldset = document.createElement("fieldset");
      fieldset.className = "question";
      fieldset.innerHTML = `<legend>${index + 1}. ${escapeHtml(question.text)}</legend>`;
      question.options.forEach(option => {
        const label = document.createElement("label");
        label.className = "option";
        label.innerHTML = `<input type="radio" name="${question.id}" value="${escapeHtml(option)}" required> ${escapeHtml(option)}`;
        fieldset.appendChild(label);
      });
      quiz.appendChild(fieldset);
    });
  } catch (error) {
    heading.after(document.createTextNode(error.message));
  }
}

authForm.addEventListener("submit", async event => {
  event.preventDefault();
  const message = document.querySelector("#authMessage");
  message.textContent = "";
  try {
    let profile = {};
    if (authMode === "register") {
      const profileAnswers = {};
      document.querySelectorAll("#accountQuiz fieldset").forEach(fieldset => {
        const selected = fieldset.querySelector("input:checked");
        if (selected) profileAnswers[fieldset.querySelector("input").name] = selected.value;
      });
      if (Object.keys(profileAnswers).length !== 10) {
        throw new Error("Answer all 10 account personality questions.");
      }
      profile = {
        name: document.querySelector("#fullName").value,
        dateOfBirth: document.querySelector("#dateOfBirth").value,
        placeOfBirth: document.querySelector("#placeOfBirth").value,
        answers: profileAnswers,
      };
    }
    await api(`/api/${authMode}`, {
      method: "POST",
      body: JSON.stringify({
        username: document.querySelector("#username").value,
        password: document.querySelector("#authPassword").value,
        ...profile,
      }),
    });
    await refreshSession();
  } catch (error) {
    message.textContent = error.message;
  }
});

document.querySelector("#logoutButton").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: "{}" });
  await refreshSession();
});

document.querySelector("#createButton").addEventListener("click", async () => {
  document.querySelector("#listView").classList.add("hidden");
  const view = document.querySelector("#quizView");
  view.classList.remove("hidden");
  try {
    const data = await api("/api/questions");
    quizForm.innerHTML = "";
    data.questions.forEach((question, index) => {
      const fieldset = document.createElement("fieldset");
      fieldset.className = "question";
      fieldset.innerHTML = `<legend>${index + 1}. ${question.text}</legend>`;
      question.options.forEach(option => {
        const label = document.createElement("label");
        label.className = "option";
        label.innerHTML = `<input type="radio" name="${question.id}" value="${escapeHtml(option)}" required> ${escapeHtml(option)}`;
        fieldset.appendChild(label);
      });
      quizForm.appendChild(fieldset);
    });
    quizForm.insertAdjacentHTML("beforeend", `
      <label>Password name
        <input id="passwordName" required maxlength="120" placeholder="Example: Email">
      </label>
      <button class="button" type="submit">Generate password</button>
    `);
  } catch (error) {
    alert(error.message);
  }
});

quizForm.addEventListener("submit", async event => {
  event.preventDefault();
  const answers = {};
  quizForm.querySelectorAll("fieldset").forEach(fieldset => {
    const selected = fieldset.querySelector("input:checked");
    if (selected) answers[fieldset.querySelector("input").name] = selected.value;
  });
  try {
    const result = await api("/api/generate", {
      method: "POST",
      body: JSON.stringify({
        name: document.querySelector("#passwordName").value,
        answers,
      }),
    });
    document.querySelector("#quizView").classList.add("hidden");
    await loadPasswords();
    alert(`Generated and saved "${result.name}".`);
  } catch (error) {
    alert(error.message);
  }
});

document.querySelector("#viewButton").addEventListener("click", async () => {
  document.querySelector("#quizView").classList.add("hidden");
  await loadPasswords();
});

async function loadPasswords() {
  const listView = document.querySelector("#listView");
  const list = document.querySelector("#passwordList");
  listView.classList.remove("hidden");
  try {
    const data = await api("/api/passwords");
    list.innerHTML = "";
    if (!data.passwords.length) {
      list.innerHTML = "<p>No saved passwords yet.</p>";
      return;
    }
    data.passwords.forEach(item => {
      const row = document.createElement("div");
      row.className = "password-row";
      row.innerHTML = `
        <div class="password-editor">
          <strong>${escapeHtml(item.name)}</strong>
          <textarea aria-label="Password for ${escapeHtml(item.name)}" rows="2">${escapeHtml(item.password)}</textarea>
        </div>
        <div class="password-tools">
          <button class="button" type="button" data-action="save">Save</button>
          <button class="button danger" type="button" data-action="delete">Delete</button>
        </div>
      `;
      row.querySelector('[data-action="save"]').addEventListener("click", async () => {
        const password = row.querySelector("textarea").value;
        try {
          await api(`/api/passwords/${encodeURIComponent(item.name)}/update`, {
            method: "POST",
            body: JSON.stringify({ password }),
          });
        } catch (error) {
          alert(error.message);
        }
      });
      row.querySelector('[data-action="delete"]').addEventListener("click", async () => {
        if (!confirm(`Delete "${item.name}"?`)) return;
        await api(`/api/passwords/${encodeURIComponent(item.name)}`, { method: "DELETE" });
        await loadPasswords();
      });
      list.appendChild(row);
    });
  } catch (error) {
    list.textContent = error.message;
  }
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value);
  return element.innerHTML;
}

refreshSession().catch(() => {});

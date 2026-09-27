// Telegram WebApp Initialization
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

// Elements
const fromInput = document.getElementById("from-input");
const fromIdInput = document.getElementById("from-id");
const fromDropdown = document.getElementById("from-dropdown");
const fromClear = document.getElementById("from-clear");

const toInput = document.getElementById("to-input");
const toIdInput = document.getElementById("to-id");
const toDropdown = document.getElementById("to-dropdown");
const toClear = document.getElementById("to-clear");

const swapBtn = document.getElementById("swap-btn");
const submitBtn = document.getElementById("submit-btn");
const resultsContainer = document.getElementById("results-container");
const resultsList = document.getElementById("results-list");
const resultsCount = document.getElementById("results-count");

// Debounce helper
function debounce(fn, delay = 150) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

// Fetch autocomplete suggestions
async function fetchStations(query) {
  if (!query || query.trim().length < 1) return [];
  try {
    const res = await fetch(`/api/stations/search?q=${encodeURIComponent(query.trim())}&limit=12`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.results || [];
  } catch (err) {
    console.error("Autocomplete fetch error:", err);
    return [];
  }
}

// Setup Autocomplete for an input
function setupAutocomplete(input, idInput, dropdown, clearBtn) {
  const onSearch = debounce(async () => {
    const query = input.value.trim();
    clearBtn.classList.toggle("visible", query.length > 0);

    // Invalidate ID if user types something new
    idInput.value = "";
    checkFormValid();

    if (query.length < 1) {
      dropdown.classList.add("hidden");
      dropdown.innerHTML = "";
      return;
    }

    const stations = await fetchStations(query);
    if (stations.length === 0) {
      dropdown.innerHTML = `<div class="dropdown-item" style="color: var(--text-muted); cursor: default;">No matching bus stand found</div>`;
      dropdown.classList.remove("hidden");
      return;
    }

    dropdown.innerHTML = "";
    stations.forEach((st) => {
      const item = document.createElement("div");
      item.className = "dropdown-item";
      item.innerHTML = `
        <span>${st.name}</span>
        ${st.depot ? `<span class="depot-tag">${st.depot}</span>` : ""}
      `;
      item.addEventListener("click", () => {
        input.value = st.name;
        idInput.value = st.id;
        dropdown.classList.add("hidden");
        dropdown.innerHTML = "";
        clearBtn.classList.add("visible");
        checkFormValid();
      });
      dropdown.appendChild(item);
    });
    dropdown.classList.remove("hidden");
  }, 150);

  input.addEventListener("input", onSearch);
  input.addEventListener("focus", () => {
    if (input.value.trim().length >= 1) {
      onSearch();
    }
  });

  clearBtn.addEventListener("click", () => {
    input.value = "";
    idInput.value = "";
    dropdown.classList.add("hidden");
    dropdown.innerHTML = "";
    clearBtn.classList.remove("visible");
    input.focus();
    checkFormValid();
  });
}

// Close dropdowns on outside click
document.addEventListener("click", (e) => {
  if (!fromInput.contains(e.target) && !fromDropdown.contains(e.target)) {
    fromDropdown.classList.add("hidden");
  }
  if (!toInput.contains(e.target) && !toDropdown.contains(e.target)) {
    toDropdown.classList.add("hidden");
  }
});

// Setup both inputs
setupAutocomplete(fromInput, fromIdInput, fromDropdown, fromClear);
setupAutocomplete(toInput, toIdInput, toDropdown, toClear);

// Swap button
swapBtn.addEventListener("click", () => {
  const tempName = fromInput.value;
  const tempId = fromIdInput.value;

  fromInput.value = toInput.value;
  fromIdInput.value = toIdInput.value;
  fromClear.classList.toggle("visible", fromInput.value.length > 0);

  toInput.value = tempName;
  toIdInput.value = tempId;
  toClear.classList.toggle("visible", toInput.value.length > 0);

  fromDropdown.classList.add("hidden");
  toDropdown.classList.add("hidden");

  checkFormValid();
});

// Check if both stations are selected
function checkFormValid() {
  const fromId = fromIdInput.value;
  const toId = toIdInput.value;
  const isValid = Boolean(fromId && toId && fromId !== toId);
  submitBtn.disabled = !isValid;
  return isValid;
}

// Form Submit Handler
submitBtn.addEventListener("click", async () => {
  if (!checkFormValid()) return;

  const payload = {
    from_id: parseInt(fromIdInput.value, 10),
    to_id: parseInt(toIdInput.value, 10),
    from_name: fromInput.value.trim(),
    to_name: toInput.value.trim(),
  };

  // If inside Telegram WebApp
  if (tg && typeof tg.sendData === "function" && tg.initData) {
    tg.sendData(JSON.stringify(payload));
    tg.close();
    return;
  }

  // Browser Fallback Mode (Preview live departures)
  submitBtn.disabled = true;
  submitBtn.textContent = "Loading Timetable...";
  try {
    const res = await fetch(`/api/routes/departures?from_id=${payload.from_id}&to_id=${payload.to_id}`);
    const data = await res.json();
    renderBrowserResults(data);
  } catch (err) {
    alert("Error fetching timetable: " + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Find Buses";
  }
});

// Render results in Browser preview
function renderBrowserResults(data) {
  resultsList.innerHTML = "";
  resultsContainer.classList.remove("hidden");
  resultsCount.textContent = data.count;

  if (data.count === 0) {
    resultsList.innerHTML = `
      <div style="padding: 16px; text-align: center; color: var(--text-muted);">
        No direct Haryana Roadways buses found for this route in official depot records.
      </div>
    `;
    return;
  }

  data.departures.forEach((dep) => {
    const card = document.createElement("div");
    card.className = "departure-card";
    card.innerHTML = `
      <div class="top-row">
        <span class="departure-time">⏰ ${dep.departure_time}</span>
        <span class="bus-badge">${dep.bus_type}</span>
      </div>
      <div class="route-info">
        <strong>${dep.route_from}</strong> &rarr; <strong>${dep.route_to}</strong>
        ${dep.route_via ? `<br><small style="color: var(--text-muted)">Via: ${dep.route_via}</small>` : ""}
      </div>
      <div class="meta-info">
        <span>Depot: ${dep.depot}</span>
        <span>${dep.service_day}</span>
      </div>
      <div style="font-size: 10px; color: var(--text-muted); margin-top: 2px;">
        Source: ${dep.source} (Verified: ${dep.last_verified_at.split(" ")[0]})
      </div>
    `;
    resultsList.appendChild(card);
  });
}

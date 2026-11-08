const statusEl = document.getElementById("save-status");
const POSITIVE_TYPES = ["income", "borrowed"];

document.querySelectorAll("table.sheet tbody tr").forEach((row) => {
  row.querySelectorAll("[data-field]").forEach((input) => {
    input.addEventListener("change", () => saveRow(row));
  });
});

async function saveRow(row) {
  const payload = {};
  row.querySelectorAll("[data-field]").forEach((input) => {
    payload[input.dataset.field] = input.value;
  });

  statusEl.textContent = "Saving...";

  try {
    const response = await fetch(row.dataset.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (data.ok) {
      statusEl.textContent = "Saved ✓";
      row.classList.remove("row-error");
      row.classList.toggle("is-positive", POSITIVE_TYPES.includes(payload.type));
    } else {
      statusEl.textContent = data.error;
      row.classList.add("row-error");
    }
  } catch (error) {
    statusEl.textContent = "Could not save. Check your connection.";
    row.classList.add("row-error");
  }
}
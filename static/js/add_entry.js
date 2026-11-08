const form = document.getElementById("entry-form");
const config = JSON.parse(form.dataset.config);

const categoryInput = document.getElementById("category");
const categoryList = document.getElementById("category-list");
const categoryLabel = document.getElementById("category-label");
const modeLabel = document.getElementById("mode-label");
const partyField = document.getElementById("party-field");
const amountInput = document.getElementById("amount");
const preview = document.getElementById("preview");
const hint = document.getElementById("type-hint");

function currentType() {
  return form.querySelector('input[name="type"]:checked').value;
}

function render() {
  const info = config[currentType()];
  categoryLabel.textContent = info.category_label;
  modeLabel.textContent = info.mode_label;
  hint.textContent = info.hint;
  partyField.hidden = !info.party;

  categoryList.innerHTML = "";
  info.categories.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    categoryList.appendChild(option);
  });
  updatePreview();
}

function updatePreview() {
  const info = config[currentType()];
  const amount = parseFloat(amountInput.value);
  if (!(amount > 0)) {
    preview.textContent = "";
    return;
  }
  const formatted = "₹" + amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  preview.textContent = info.sign > 0
    ? `Adds ${formatted} to your balance`
    : `Deducts ${formatted} from your balance`;
  preview.className = "preview " + (info.sign > 0 ? "pos" : "neg");
}

form.querySelectorAll('input[name="type"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    categoryInput.value = "";
    render();
  });
});
amountInput.addEventListener("input", updatePreview);

render();
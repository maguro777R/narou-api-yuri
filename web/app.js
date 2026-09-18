"use strict";

// 数字は HTML に描画済み。閲覧者のブラウザから API を取得しない。
const ageGate = document.querySelector("#age-gate");
const expiresAt = Date.parse(document.body.dataset.expires);
let ageConfirmed = !ageGate;
let genreSelect;
let statusInputs = [];
let observations = [];

function checkFreshness() {
  if (!Number.isFinite(expiresAt)) return false;
  const expired = Date.now() >= expiresAt;
  document.querySelector("#live-content").hidden = expired || !ageConfirmed;
  document.querySelector("#expired").hidden = !expired;
  if (ageGate) ageGate.hidden = expired || ageConfirmed;
  const warning = document.querySelector("#update-warning");
  if (warning) warning.hidden = Date.now() < expiresAt - 6 * 24 * 60 * 60 * 1000;
  return expired;
}

function updateSelection(writeUrl = true) {
  const status = statusInputs.find((input) => input.checked)?.value || "all";
  let visible;
  for (const section of observations) {
    section.hidden = section.dataset.genre !== genreSelect.value || section.dataset.status !== status;
    section.querySelector(".keyword-card")?.removeAttribute("id");
    section.querySelector(".books-card")?.removeAttribute("id");
    if (!section.hidden) visible = section;
  }
  if (!visible) return;
  visible.querySelector(".keyword-card").id = "keywords";
  visible.querySelector(".books-card").id = "stories";
  document.querySelector("#selection-status").textContent = visible.querySelector(".scope").textContent;
  if (writeUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("genre", genreSelect.value);
    url.searchParams.set("status", status);
    history.replaceState(null, "", url);
  }
}

function initializeFilters() {
  genreSelect = document.querySelector("#genre");
  if (!genreSelect) return;
  statusInputs = [...document.querySelectorAll('input[name="status"]')];
  observations = [...document.querySelectorAll(".observation")];
  const params = new URLSearchParams(window.location.search);
  if ([...genreSelect.options].some((option) => option.value === params.get("genre"))) {
    genreSelect.value = params.get("genre");
  }
  for (const input of statusInputs) {
    if (input.value === params.get("status")) input.checked = true;
    input.addEventListener("change", () => updateSelection());
  }
  genreSelect.addEventListener("change", () => updateSelection());
  updateSelection(false);
}

if (ageGate) {
  document.querySelector("#confirm-age").addEventListener("click", () => {
    if (checkFreshness()) return;
    const template = document.querySelector("#adult-content");
    document.querySelector("#live-content").append(template.content.cloneNode(true));
    template.remove();
    ageConfirmed = true;
    initializeFilters();
    checkFreshness();
    genreSelect?.focus();
  });
} else {
  initializeFilters();
}

for (const link of document.querySelectorAll(".nav-link")) {
  link.addEventListener("click", () => {
    document.querySelector(".nav-link.active")?.classList.remove("active");
    link.classList.add("active");
  });
}
checkFreshness();
// 開きっぱなしでも確認前の R18 データや期限切れの情報を表示しない。
setInterval(checkFreshness, 60_000);
document.addEventListener("visibilitychange", checkFreshness);

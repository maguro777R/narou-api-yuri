"use strict";

// 数字は HTML に描画済み。閲覧者のブラウザから API を取得しない。
const genreSelect = document.querySelector("#genre");
const statusInputs = [...document.querySelectorAll('input[name="status"]')];
const observations = [...document.querySelectorAll(".observation")];
const expiresAt = Date.parse(document.body.dataset.expires);

function checkFreshness() {
  if (!Number.isFinite(expiresAt)) return false;
  const expired = Date.now() >= expiresAt;
  document.querySelector("#live-content").hidden = expired;
  document.querySelector("#expired").hidden = !expired;
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

if (genreSelect) {
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

for (const link of document.querySelectorAll(".nav-link")) {
  link.addEventListener("click", () => {
    document.querySelector(".nav-link.active")?.classList.remove("active");
    link.classList.add("active");
  });
}
checkFreshness();
// ページを開きっぱなしにした場合も、古くなったデータを表示し続けない。
setInterval(checkFreshness, 60_000);
document.addEventListener("visibilitychange", checkFreshness);

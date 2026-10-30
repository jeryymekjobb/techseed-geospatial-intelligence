// The map's source credits, out of the map picture
// (reports/2026-10-30-kreditering-utanfor-kartbilden-claude-opus-5-5.md): the whole list in the
// scenario's summary and closing view and behind "(i) Källor" in the map's corner, where only
// OpenStreetMap's credit and a shown municipal map's stay in sight. The credits are the
// scenario's own texts, some with links, so they are drawn as HTML.
"use strict";

const OSM_CREDIT = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap-bidragsgivare</a>';

// OpenStreetMap's credit in the list: the layers' own variants, with and without a link, are one source.
const OSM_LIST_CREDIT = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a> (ODbL)';

const creditState = { all: [], short: [], open: false };

// The text a credit is listed with.
function listedCredit(text) {
  const plain = text.replace(/<[^>]*>/g, "").replace(/&copy;/g, "©").trim();
  return /^© OpenStreetMap contributors( \(ODbL\))?$/.test(plain) ? OSM_LIST_CREDIT : text;
}

// A source's credit, once, in the order the map met it.
function addCredit(text) {
  if (!text) return;
  const listed = listedCredit(text);
  if (creditState.all.includes(listed)) return;
  creditState.all.push(listed);
  renderCredits();
}

// The credits that stay in sight beside OpenStreetMap's: the shown municipal map's.
function setShortCredits(texts) {
  creditState.short = texts.filter(Boolean);
  for (const text of creditState.short) addCredit(text);
  renderCredits();
}

// The line in the map's corner and, when opened, the list under it.
function creditBox(element = document.createElement("div")) {
  element.classList.add("map-credits");
  element.innerHTML = '<span class="credit-short"></span> · <button type="button" class="credit-toggle"></button><ul class="credit-list" hidden></ul>';
  element.querySelector(".credit-toggle").addEventListener("click", (event) => {
    event.stopPropagation();
    creditState.open = !creditState.open;
    renderCredits();
  });
  renderCredits(element);
  return element;
}

// The whole list, for the summary and the closing view; filled again as credits come.
function creditList() {
  const section = document.createElement("div");
  section.className = "credit-section";
  section.innerHTML = '<h3>Källor</h3><ul class="credit-list"></ul>';
  renderCredits(section);
  return section;
}

function renderCredits(root = document) {
  for (const short of root.querySelectorAll(".credit-short")) {
    short.innerHTML = [OSM_CREDIT, ...creditState.short].join(" · ");
  }
  for (const toggle of root.querySelectorAll(".credit-toggle")) {
    toggle.textContent = creditState.open ? "(i) Dölj källor" : "(i) Källor";
    toggle.ariaExpanded = String(creditState.open);
  }
  for (const list of root.querySelectorAll(".credit-list")) {
    list.innerHTML = creditState.all.map((text) => `<li>${text}</li>`).join("");
    if (list.closest(".map-credits")) list.hidden = !creditState.open;
  }
}

if (typeof module !== "undefined") module.exports = { listedCredit };

// Copernicus EMS's mapped perimeters of the fire (/api/ems, app/backend/ems.py): the newest
// product shown by the scenario clock, and its text. Pure, so it can be tested in Node.
"use strict";

function emsAt(products, clockMs) {
  let found = null;
  for (const product of products) {
    if (Date.parse(product.visible_from_utc) <= clockMs) found = product;
  }
  return found;
}

// "SPOT-6/7-bild 20 juli 2018, 8 575 ha"
function emsText(product, formatDate) {
  const source = product.image_source === "SPOT-6-7" ? "SPOT-6/7" : product.image_source;
  return `${source}-bild ${formatDate(product.image_date)}, ${product.area_ha.toLocaleString("sv-SE")} ha`;
}

if (typeof module !== "undefined") module.exports = { emsAt, emsText };

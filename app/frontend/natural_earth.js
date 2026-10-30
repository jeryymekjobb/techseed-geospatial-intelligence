// The 2D map's world outside the offline map, as on the 3D globe: Natural Earth II from Cesium's own
// copy (geographic 256 px tiles, levels 0–2), redrawn row by row into Leaflet's Web Mercator tiles,
// and the offline map cut at its map area, as Cesium's rectangle cuts it. The arithmetic is pure, so
// it can be tested in Node.
"use strict";

const NATURAL_EARTH_URL = "/vendor/cesium-1.146.0/Assets/Textures/NaturalEarthII";
const NATURAL_EARTH_LEVEL = 2;  // 8 x 4 tiles: 2048 x 1024 px over the world

// The latitude at a share of Web Mercator's height (0 at its north edge, 1 at its south).
function mercatorLatitude(share) {
  return (Math.atan(Math.sinh(Math.PI * (1 - 2 * share))) * 180) / Math.PI;
}

// A point's pixel in the Web Mercator world at zoom z with tiles `size` px.
function mercatorPixel(lat, lon, z, size) {
  const world = size * 2 ** z;
  const sin = Math.sin((lat * Math.PI) / 180);
  return {
    x: ((lon + 180) / 360) * world,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * world,
  };
}

// The part of tile {x, y, z} (`size` px) inside bounds [[south, west], [north, east]], in the tile's
// pixels, or null when none is.
function tileClip(tile, size, bounds) {
  const [[south, west], [north, east]] = bounds;
  const low = mercatorPixel(south, west, tile.z, size);
  const high = mercatorPixel(north, east, tile.z, size);
  const clamp = (value) => Math.min(Math.max(value, 0), size);
  const left = clamp(Math.floor(low.x - tile.x * size));
  const right = clamp(Math.ceil(high.x - tile.x * size));
  const top = clamp(Math.floor(high.y - tile.y * size));
  const bottom = clamp(Math.ceil(low.y - tile.y * size));
  return left < right && top < bottom ? { left, top, width: right - left, height: bottom - top } : null;
}

// Natural Earth II's level as one image from 90 N to 90 S; its tiles count rows from the south.
let naturalEarthWorld = null;
function loadNaturalEarth() {
  if (naturalEarthWorld) return naturalEarthWorld;
  const columns = 2 ** (NATURAL_EARTH_LEVEL + 1);
  const rows = 2 ** NATURAL_EARTH_LEVEL;
  const world = document.createElement("canvas");
  world.width = columns * 256;
  world.height = rows * 256;
  const context = world.getContext("2d");
  const tiles = [];
  for (let x = 0; x < columns; x += 1) {
    for (let y = 0; y < rows; y += 1) {
      tiles.push(new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => { context.drawImage(image, x * 256, (rows - 1 - y) * 256); resolve(); };
        image.onerror = reject;
        image.src = `${NATURAL_EARTH_URL}/${NATURAL_EARTH_LEVEL}/${x}/${y}.jpg`;
      }));
    }
  }
  naturalEarthWorld = Promise.all(tiles).then(() => world);
  return naturalEarthWorld;
}

function naturalEarthLayer(options) {
  const Layer = L.GridLayer.extend({
    createTile(coords, done) {
      const size = this.getTileSize().x;
      const tile = document.createElement("canvas");
      tile.width = tile.height = size;
      loadNaturalEarth().then((world) => {
        const context = tile.getContext("2d");
        const count = 2 ** coords.z;
        const width = world.width / count;
        // Each row blends the two nearest of the world's rows, so a coarse row is no stripe up close.
        for (let row = 0; row < size; row += 1) {
          const latitude = mercatorLatitude((coords.y * size + row + 0.5) / (count * size));
          const source = Math.min(Math.max(((90 - latitude) / 180) * world.height - 0.5, 0), world.height - 1);
          const above = Math.floor(source);
          const below = Math.min(above + 1, world.height - 1);
          context.globalAlpha = 1;
          context.drawImage(world, coords.x * width, above, width, 1, 0, row, size, 1);
          context.globalAlpha = source - above;
          context.drawImage(world, coords.x * width, below, width, 1, 0, row, size, 1);
        }
        context.globalAlpha = 1;
        done(null, tile);
      }, (error) => done(error, tile));
      return tile;
    },
  });
  return new Layer(options);
}

// A tile layer drawn only inside bounds [[south, west], [north, east]]: a coarse tile is about as
// large as a country, and the offline map's land colour fills it all around the map area.
function clippedTileLayer(url, bounds, options) {
  const Layer = L.TileLayer.extend({
    createTile(coords, done) {
      const size = this.getTileSize().x;
      const tile = document.createElement("canvas");
      tile.width = tile.height = size;
      const clip = tileClip(coords, size, bounds);
      if (!clip) {
        done(null, tile);
        return tile;
      }
      const image = new Image();
      image.onload = () => {
        tile.getContext("2d").drawImage(image, clip.left, clip.top, clip.width, clip.height,
          clip.left, clip.top, clip.width, clip.height);
        done(null, tile);
      };
      image.onerror = (error) => done(error, tile);
      image.src = this.getTileUrl(coords);
      return tile;
    },
  });
  return new Layer(url, { ...options, bounds });
}

if (typeof module !== "undefined") module.exports = { mercatorLatitude, mercatorPixel, tileClip };

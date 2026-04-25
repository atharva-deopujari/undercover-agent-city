// ===========================================================================
// City data: grid layout + lookups (mirrors server/city_data.py)
// ===========================================================================

const TERRAIN = {
  ROAD:      0,
  BUILDING:  1,
  ALLEY:     2,
  SHOP:      3,
  PARK:      4,
  HIDEOUT:   5,
  POLICE:    6,
  WAREHOUSE: 7,
  SAFE_HOUSE:8,
  SIDEWALK:  9,  // visual-only: 1-tile band on either side of every road, paved
};

const TERRAIN_NAMES = ["road","building","alley","shop","park","hideout","police","warehouse","safe_house","sidewalk"];

function buildGrid() {
  const W = 15, H = 15;
  const g = new Array(W * H).fill(TERRAIN.BUILDING);

  // Road rows + cols (1 tile wide logical roads — backend-compatible)
  const roadRows = [2, 5, 8, 11];
  const roadCols = [4, 8];
  for (const y of roadRows) for (let x = 0; x < W; x++) g[y * W + x] = TERRAIN.ROAD;
  for (const x of roadCols) for (let y = 0; y < H; y++) g[y * W + x] = TERRAIN.ROAD;
  // Top entrance
  for (let x = 4; x <= 8; x++) g[0 * W + x] = TERRAIN.ROAD;

  // Sidewalks: 1-tile band on either side of each road, but only over existing
  // building tiles (don't overwrite specials or roads).
  const setIfBuilding = (x, y, t) => {
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    if (g[y * W + x] === TERRAIN.BUILDING) g[y * W + x] = t;
  };
  for (const y of roadRows) {
    for (let x = 0; x < W; x++) {
      setIfBuilding(x, y - 1, TERRAIN.SIDEWALK);
      setIfBuilding(x, y + 1, TERRAIN.SIDEWALK);
    }
  }
  for (const x of roadCols) {
    for (let y = 0; y < H; y++) {
      setIfBuilding(x - 1, y, TERRAIN.SIDEWALK);
      setIfBuilding(x + 1, y, TERRAIN.SIDEWALK);
    }
  }

  // Scatter extra parks (open grass + tree) over remaining building tiles.
  // These break up dense blocks and give us places to spawn trees.
  const extraParks = [
    [10, 3], [13, 3], [13, 7], [9, 12], [12, 12], [3, 12],
    [13, 10], [9, 6], [7, 14], [11, 14],
  ];
  for (const [x, y] of extraParks) {
    if (g[y * W + x] === TERRAIN.BUILDING) g[y * W + x] = TERRAIN.PARK;
  }

  // Specials (placed last so they win over sidewalks)
  const specials = [
    [1, 1, TERRAIN.SHOP],
    [11, 1, TERRAIN.SHOP],
    [6, 3, TERRAIN.SHOP],
    [2, 4, TERRAIN.PARK],
    [5, 13, TERRAIN.PARK],
    [1, 7, TERRAIN.HIDEOUT],
    [11, 10, TERRAIN.HIDEOUT],
    [1, 13, TERRAIN.POLICE],
    [6, 9, TERRAIN.WAREHOUSE],
    [12, 4, TERRAIN.SAFE_HOUSE],
    [13, 13, TERRAIN.SAFE_HOUSE],
  ];
  for (const [x, y, t] of specials) g[y * W + x] = t;

  return g;
}

function getDistrict(y) {
  if (y <= 4) return "downtown";
  if (y <= 9) return "docks";
  return "residential";
}

window.GRID = buildGrid();
window.GRID_W = 15;
window.GRID_H = 15;
window.TERRAIN = TERRAIN;
window.TERRAIN_NAMES = TERRAIN_NAMES;
window.getDistrict = getDistrict;

'use strict';

const SHIPS = [5, 4, 3, 3, 2]; // lengths

function createGrid() {
  return Array.from({length: 10}, () => Array(10).fill(0));
}

function placeShipsRandom(grid) {
  const placed = [];
  for (const len of SHIPS) {
    let ok = false, tries = 0;
    while (!ok && tries++ < 500) {
      const dir = Math.random() < 0.5 ? 'h' : 'v';
      const row = Math.floor(Math.random() * 10);
      const col = Math.floor(Math.random() * 10);
      if (canPlace(grid, row, col, len, dir)) {
        const cells = [];
        for (let i = 0; i < len; i++) {
          const r = dir === 'v' ? row + i : row;
          const c = dir === 'h' ? col + i : col;
          grid[r][c] = 1;
          cells.push([r, c]);
        }
        placed.push(cells);
        ok = true;
      }
    }
  }
  return placed;
}

function canPlace(grid, row, col, len, dir) {
  for (let i = 0; i < len; i++) {
    const r = dir === 'v' ? row + i : row;
    const c = dir === 'h' ? col + i : col;
    if (r >= 10 || c >= 10) return false;
    for (let dr = -1; dr <= 1; dr++)
      for (let dc = -1; dc <= 1; dc++) {
        const nr = r + dr, nc = c + dc;
        if (nr >= 0 && nr < 10 && nc >= 0 && nc < 10 && grid[nr][nc]) return false;
      }
  }
  return true;
}

// ── State ────────────────────────────────────────────────────────────────────

let playerGrid, enemyGrid, enemyShips;
let playerHits = {}, enemyHits = {};
let hits = 0, gameOver = false;
const TOTAL = SHIPS.reduce((a, b) => a + b, 0);

function initGame() {
  playerGrid = createGrid();
  enemyGrid  = createGrid();
  playerHits = {};
  enemyHits  = {};
  hits = 0;
  gameOver = false;
  placeShipsRandom(playerGrid);
  enemyShips = placeShipsRandom(enemyGrid);
  renderBoards();
  setStatus('Your turn — click enemy waters!');
  document.getElementById('score').textContent = `Hits: 0 / ${TOTAL}`;
}

// ── Rendering ────────────────────────────────────────────────────────────────

function renderBoards() {
  renderBoard('player-board', playerGrid, playerHits, false);
  renderBoard('enemy-board',  enemyGrid,  enemyHits,  true);
}

function renderBoard(id, grid, hitMap, isEnemy) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  for (let r = 0; r < 10; r++) {
    for (let c = 0; c < 10; c++) {
      const cell = document.createElement('div');
      cell.className = 'cell';
      const key = `${r},${c}`;
      if (hitMap[key] === 'hit')  cell.classList.add('hit');
      else if (hitMap[key] === 'miss') cell.classList.add('miss');
      else if (!isEnemy && grid[r][c]) cell.classList.add('ship');
      if (isEnemy && !gameOver) {
        cell.addEventListener('click', () => playerFire(r, c));
      }
      el.appendChild(cell);
    }
  }
}

// ── Gameplay ──────────────────────────────────────────────────────────────────

function playerFire(r, c) {
  if (gameOver) return;
  const key = `${r},${c}`;
  if (enemyHits[key]) return;
  if (enemyGrid[r][c]) {
    enemyHits[key] = 'hit';
    hits++;
    document.getElementById('score').textContent = `Hits: ${hits} / ${TOTAL}`;
    if (hits >= TOTAL) { endGame(true); return; }
    setStatus('Hit! 🔥 Fire again!');
  } else {
    enemyHits[key] = 'miss';
    setStatus('Miss. Enemy fires...');
    setTimeout(enemyFire, 500);
  }
  renderBoards();
}

function enemyFire() {
  if (gameOver) return;
  let r, c, key;
  do {
    r = Math.floor(Math.random() * 10);
    c = Math.floor(Math.random() * 10);
    key = `${r},${c}`;
  } while (playerHits[key]);
  if (playerGrid[r][c]) {
    playerHits[key] = 'hit';
    const sunk = Object.values(playerHits).filter(v => v === 'hit').length;
    if (sunk >= TOTAL) { endGame(false); return; }
    setStatus('Enemy hit your ship! ⚡ Your turn.');
  } else {
    playerHits[key] = 'miss';
    setStatus('Enemy missed. Your turn!');
  }
  renderBoards();
}

function endGame(won) {
  gameOver = true;
  // Reveal enemy ships
  for (let r = 0; r < 10; r++)
    for (let c = 0; c < 10; c++)
      if (enemyGrid[r][c] && !enemyHits[`${r},${c}`]) enemyHits[`${r},${c}`] = 'ship';
  renderBoards();
  setStatus(won ? '🎉 You won! All enemy ships sunk!' : '💀 You lost! Enemy sunk your fleet.');
}

function setStatus(msg) {
  document.getElementById('status').textContent = msg;
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.getElementById('btn-new').addEventListener('click', initGame);
initGame();

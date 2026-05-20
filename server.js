const express = require('express');
const path = require('path');
const fs = require('fs');
const Database = require('better-sqlite3');
const seed = require('./seed');

const db = new Database(path.join(__dirname, 'data.db'));
db.exec(`
  CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

const existing = db.prepare('SELECT data FROM content WHERE id = 1').get();
if (!existing) {
  db.prepare('INSERT INTO content (id, data) VALUES (1, ?)').run(JSON.stringify(seed));
}

const readData = () => JSON.parse(db.prepare('SELECT data FROM content WHERE id = 1').get().data);
const writeData = (data) => db.prepare("UPDATE content SET data = ?, updated_at = datetime('now') WHERE id = 1").run(JSON.stringify(data));

const template = fs.readFileSync(path.join(__dirname, 'views', 'index.html'), 'utf8');
const render = (editable) => template.replace('__EDITABLE__', editable ? 'true' : 'false');

const app = express();
app.use(express.json({ limit: '2mb' }));

app.get('/', (_req, res) => res.type('html').send(render(false)));
app.get('/edit', (_req, res) => res.type('html').send(render(true)));

app.get('/api/data', (_req, res) => res.json(readData()));

app.put('/api/data', (req, res) => {
  if (!req.body || typeof req.body !== 'object') return res.status(400).json({ error: 'invalid body' });
  writeData(req.body);
  res.json({ ok: true });
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`Maturity curve on http://localhost:${port} (edit: /edit)`));

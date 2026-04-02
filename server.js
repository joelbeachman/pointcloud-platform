const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Serve data directory (point clouds, splats, panoramas)
app.use('/data', express.static(path.join(__dirname, 'data')));

// API: list all datasets
app.get('/api/datasets', (req, res) => {
  const dbPath = path.join(__dirname, 'data', 'datasets.json');
  if (!fs.existsSync(dbPath)) {
    return res.json([]);
  }
  const datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  res.json(datasets);
});

// API: get single dataset
app.get('/api/datasets/:id', (req, res) => {
  const dbPath = path.join(__dirname, 'data', 'datasets.json');
  if (!fs.existsSync(dbPath)) return res.status(404).json({ error: 'Not found' });
  const datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  const dataset = datasets.find(d => d.id === req.params.id);
  if (!dataset) return res.status(404).json({ error: 'Not found' });
  res.json(dataset);
});

// API: register a dataset
app.post('/api/datasets', (req, res) => {
  const dbPath = path.join(__dirname, 'data', 'datasets.json');
  const datasets = fs.existsSync(dbPath)
    ? JSON.parse(fs.readFileSync(dbPath, 'utf8'))
    : [];
  const dataset = { ...req.body, id: req.body.id || Date.now().toString(), createdAt: new Date().toISOString() };
  datasets.push(dataset);
  fs.writeFileSync(dbPath, JSON.stringify(datasets, null, 2));
  res.json(dataset);
});

// API: delete a dataset
app.delete('/api/datasets/:id', (req, res) => {
  const dbPath = path.join(__dirname, 'data', 'datasets.json');
  if (!fs.existsSync(dbPath)) return res.status(404).json({ error: 'Not found' });
  let datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  datasets = datasets.filter(d => d.id !== req.params.id);
  fs.writeFileSync(dbPath, JSON.stringify(datasets, null, 2));
  res.json({ ok: true });
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`Point Cloud Platform running at http://localhost:${PORT}`);
});

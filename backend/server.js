require('dotenv').config();
const express = require('express');
const cors    = require('cors');
const path    = require('path');
const fs      = require('fs');

const app  = express();
const PORT = process.env.PORT || 3001;

// ── Ensure folders exist ───────────────────────────────────────
const UPLOADS = path.join(__dirname, 'uploads');
const DATA    = path.join(__dirname, 'data');
[UPLOADS, DATA].forEach(d => { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); });

// ── Middleware ─────────────────────────────────────────────────
app.use(cors({ origin: '*', methods: ['GET','POST','PUT','DELETE','OPTIONS'], allowedHeaders: ['Content-Type','Authorization'] }));
app.options('*', cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Request logger
app.use((req, res, next) => {
  res.on('finish', () => {
    const icon = res.statusCode >= 400 ? '❌' : '✅';
    if (!req.path.includes('/health')) {
      console.log(`${icon} ${req.method} ${req.path} → ${res.statusCode}`);
    }
  });
  next();
});

// ── Static files ───────────────────────────────────────────────
app.use('/uploads', express.static(UPLOADS));
app.use(express.static(path.join(__dirname, '../frontend')));

// ── Auth routes (public) ───────────────────────────────────────
app.use('/api/auth', require('./routes/auth'));

// ── Protected routes ───────────────────────────────────────────
const { requireAuth } = require('./middleware/auth');
app.use('/api/upload',     requireAuth, require('./routes/upload'));
app.use('/api/documents',  requireAuth, require('./routes/documents'));
app.use('/api/chat',       requireAuth, require('./routes/chat'));
app.use('/api/summary',    requireAuth, require('./routes/summary'));
app.use('/api/flashcards', requireAuth, require('./routes/flashcards'));
app.use('/api/podcast',    requireAuth, require('./routes/podcast'));

// ── Health check ───────────────────────────────────────────────
app.get('/api/health', (req, res) => {
  res.json({
    status:   'ok',
    version:  '2.0.0',
    groqKey:  process.env.GROQ_API_KEY ? '✅ set' : '❌ MISSING — add to .env',
    jwt:      process.env.JWT_SECRET   ? '✅ set' : '⚠️  using default',
    docs:     require('./utils/store').getAllDocs().length,
    users:    require('./utils/userStore').count(),
    uptime:   Math.round(process.uptime()) + 's',
  });
});

// ── Fallback: serve frontend ───────────────────────────────────
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../frontend/index.html'));
});

// ── Global error handler ───────────────────────────────────────
app.use((err, req, res, next) => {
  console.error('Server error:', err.message);
  res.status(err.status || 500).json({ error: err.message });
});

// ── Start + rehydrate ──────────────────────────────────────────
app.listen(PORT, '0.0.0.0', async () => {
  console.log(`\n🚀 Saathi AI v2 running → port ${PORT}`);
  console.log(`🔑 Groq API Key: ${process.env.GROQ_API_KEY ? 'SET ✅' : 'MISSING ❌ — add to environment variables'}`);
  console.log(`🔐 JWT Secret:   ${process.env.JWT_SECRET ? 'SET ✅' : 'using default ⚠️'}`);
  console.log(`📁 Uploads:      ${UPLOADS}\n`);

  // Rehydrate vector store from disk on restart
  const { rehydrate } = require('./services/docService');
  const docs = require('./utils/store').getAllDocs();

  if (docs.length > 0) {
    await rehydrate(docs);
  }
});
module.exports = app;

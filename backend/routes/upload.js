const router = require('express').Router();
const multer = require('multer');
const path = require('path');
const { v4: uuid } = require('uuid');

const docSvc = require('../services/docService');
const store = require('../utils/store');

// ── Multer storage ─────────────────────────────────────────────
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, path.join(__dirname, '../uploads'));
  },

  filename: (req, file, cb) => {
    cb(
      null,
      uuid() + path.extname(file.originalname)
    );
  },
});

// ── Upload configuration ──────────────────────────────────────
const upload = multer({
  storage,

  limits: {
    fileSize: 50 * 1024 * 1024
  },

  fileFilter: (req, file, cb) => {
    const ext = path
      .extname(file.originalname)
      .toLowerCase();

    const allowed = ['.pdf', '.txt', '.md'];

    if (allowed.includes(ext)) {
      cb(null, true);
    } else {
      cb(
        new Error(
          'File type not supported. Use PDF, TXT, or MD.'
        )
      );
    }
  },
});

// ── Upload route ───────────────────────────────────────────────
router.post(
  '/',
  (req, res, next) => {

    upload.array('files', 10)(
      req,
      res,
      err => {

        if (err) {
          console.error('❌ Multer error:', err);

          return res.status(400).json({
            error: err.message
          });
        }

        next();
      }
    );
  },

  async (req, res) => {

    if (!req.files || req.files.length === 0) {
      return res.status(400).json({
        error: 'No files received'
      });
    }

    const uploaded = [];
    const errors = [];

    // ── Process uploaded files ────────────────────────────────
    for (const file of req.files) {

      const docId = path.basename(
        file.filename,
        path.extname(file.filename)
      );

      try {

        console.log(
          `\n📄 Ingesting uploaded file: ${file.originalname}`
        );

        console.log(
          `   Saved path: ${file.path}`
        );

        console.log(
          `   File size: ${file.size} bytes`
        );

        // ── Run document ingestion ─────────────────────────
        const result = await docSvc.ingest(
          file.path,
          docId,
          file.originalname
        );

        // ── Save document metadata ──────────────────────────
        store.addDoc({
          id: docId,
          name: file.filename,
          originalName: file.originalname,
          size: file.size,
          filePath: file.path,
          pageCount: result.pageCount,
          chunkCount: result.chunkCount,
          preview: result.preview,
          status: 'ready',
        });

        // ── Successful upload ───────────────────────────────
        uploaded.push({
          id: docId,
          name: file.originalname,
          pageCount: result.pageCount,
          chunkCount: result.chunkCount
        });

        console.log(
          `✅ Upload successful: ${file.originalname}`
        );

      } catch (e) {

        console.error('\n❌ UPLOAD ERROR');
        console.error('File:', file.originalname);
        console.error('Path:', file.path);
        console.error('Size:', file.size);
        console.error('Message:', e.message);
        console.error('Stack:', e.stack);

        errors.push({
          file: file.originalname,
          error: e.message
        });
      }
    }

    // ── Response ──────────────────────────────────────────────
    return res.json({
      uploaded,
      errors,
      message:
        `${uploaded.length}/${req.files.length} files processed`
    });
  }
);

module.exports = router;
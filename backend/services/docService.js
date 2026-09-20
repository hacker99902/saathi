/**
 * Saathi AI - Document Service
 * Extracts text from PDF/TXT/MD and ingests into vector store.
 */

const fs = require('fs');
const path = require('path');

const { chunkText } = require('../utils/chunker');
const store = require('../vectorStore/memoryStore');

// pdf-parse v2
const { PDFParse } = require('pdf-parse');

console.log('✅ pdf-parse v2 ready');


// ── Extract text ───────────────────────────────────────────────
async function extractText(filePath, originalName) {

  const ext = path
    .extname(originalName)
    .toLowerCase();


  // ── PDF ─────────────────────────────────────────────────────
  if (ext === '.pdf') {

    const buffer = fs.readFileSync(filePath);

    if (!buffer || buffer.length === 0) {
      throw new Error('PDF file is empty.');
    }

    console.log(
      `📖 Parsing PDF: ${originalName} (${buffer.length} bytes)`
    );

    const parser = new PDFParse({
      data: buffer
    });

    try {

      const result = await parser.getText();

      const text = result.text || '';

      const pageCount =
        result.total ||
        result.numpages ||
        1;

      console.log(
        `   PDF parsed: ${pageCount} pages, ${text.length} chars`
      );

      return {
        text,
        pageCount
      };

    } finally {

      // Release parser resources
      await parser.destroy();
    }
  }


  // ── TXT / Markdown ─────────────────────────────────────────
  if (ext === '.txt' || ext === '.md') {

    const text = fs.readFileSync(
      filePath,
      'utf8'
    );

    return {
      text,
      pageCount: Math.max(
        1,
        Math.ceil(text.length / 2000)
      )
    };
  }


  throw new Error(
    `Unsupported file type: ${ext}. Use PDF, TXT or MD.`
  );
}


// ── Main ingestion pipeline ───────────────────────────────────
async function ingest(
  filePath,
  docId,
  originalName
) {

  console.log(
    `📄 Ingesting: ${originalName}`
  );

  const {
    text,
    pageCount
  } = await extractText(
    filePath,
    originalName
  );


  // Check extracted text
  if (
    !text ||
    text.trim().length < 20
  ) {

    throw new Error(
      'Document has no readable text. ' +
      'It may be a scanned/image PDF. ' +
      'Only text-based PDFs are supported.'
    );
  }


  console.log(
    `   Extracted: ${text.length} chars, ${pageCount} pages`
  );


  // ── Chunk document ──────────────────────────────────────────
  const chunkSize =
    text.length < 5000
      ? 300
      : 500;

  const chunks = chunkText(
    text,
    chunkSize,
    60
  );


  if (!chunks.length) {
    throw new Error(
      'Could not create chunks from document'
    );
  }


  // Add docId to every chunk
  const tagged = chunks.map(
    chunk => ({
      ...chunk,
      docId
    })
  );


  // ── Store vectors ───────────────────────────────────────────
  await store.addChunks(
    `doc_${docId}`,
    tagged
  );


  console.log(
    `✅ Ingested ${chunks.length} chunks from "${originalName}"`
  );


  return {
    chunkCount: chunks.length,
    pageCount,

    preview: text
      .slice(0, 200)
      .replace(/\s+/g, ' ')
      .trim(),

    fullText: text
  };
}


// ── Retrieve relevant chunks ───────────────────────────────────
async function retrieve(
  docIds,
  query,
  n = 6
) {

  if (docIds.length === 1) {

    return store.query(
      `doc_${docIds[0]}`,
      query,
      n
    );
  }

  return store.queryMultiple(
    docIds.map(
      id => `doc_${id}`
    ),
    query,
    n
  );
}


// ── Delete document ────────────────────────────────────────────
async function deleteDoc(docId) {

  await store.deleteCollection(
    `doc_${docId}`
  );
}


// ── Rehydrate documents after restart ─────────────────────────
async function rehydrate(documents) {

  if (
    !documents ||
    documents.length === 0
  ) {
    return;
  }

  console.log(
    `🔄 Rehydrating ${documents.length} document(s) from disk...`
  );


  for (const doc of documents) {

    if (
      !doc.filePath ||
      !fs.existsSync(doc.filePath)
    ) {
      continue;
    }

    try {

      await ingest(
        doc.filePath,
        doc.id,
        doc.originalName
      );

    } catch (e) {

      console.warn(
        `⚠️ Could not rehydrate ${doc.originalName}:`,
        e.message
      );
    }
  }


  console.log(
    '✅ Rehydration complete'
  );
}


module.exports = {
  ingest,
  retrieve,
  deleteDoc,
  extractText,
  rehydrate
};
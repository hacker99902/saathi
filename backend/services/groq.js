/**
 * Saathi AI - Groq LLM Service
 * All AI completions: chat, summary, flashcards, podcast, exam.
 */
const axios = require('axios');

const URL     = 'https://api.groq.com/openai/v1/chat/completions';
const MODEL  = 'llama-3.3-70b-versatile';
const BACKUP = 'openai/gpt-oss-20b';

async function call(messages, opts = {}) {
  const { model = MODEL, temperature = 0.3, maxTokens = 2048 } = opts;
  const key = process.env.GROQ_API_KEY;
  if (!key) throw new Error('GROQ_API_KEY not set in .env file');

  try {
    const res = await axios.post(URL, {
      model, messages, temperature, max_tokens: maxTokens
    }, {
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      timeout: 60000,
    });
    return res.data.choices[0].message.content;
  } catch (e) {
    if (model === MODEL) return call(messages, { ...opts, model: BACKUP });
    const msg = e.response?.data?.error?.message || e.message;
    throw new Error(`Groq API error: ${msg}`);
  }
}

// ── RAG Chat ──────────────────────────────────────────────────
async function ragChat(query, chunks, history = []) {
  const context = chunks
    .map((c, i) => `[Source ${i+1} | Page ${c.page}]:\n${c.text}`)
    .join('\n\n');

  const histMsgs = history.slice(-6).map(m => ({ role: m.role, content: m.content }));

  const sys = `You are Saathi, an expert AI research assistant. Answer questions using ONLY the provided document context below.

RULES:
- Answer ONLY from the context. Never use outside knowledge.
- Always cite sources like [Page 2] inline.
- Format your response as:
  **Answer:** [your detailed answer with citations like [Page 2]]
  
  **Sources:**
  - Page X: "exact quote from page"
- If the context doesn't contain the answer, say: "This information is not in the provided document."
- Be precise, helpful, and academic.`;

  const user = `Document Context:\n${context}\n\nQuestion: ${query}`;

  return call([{ role: 'system', content: sys }, ...histMsgs, { role: 'user', content: user }],
    { temperature: 0.2, maxTokens: 1500 });
}

// ── Summary ───────────────────────────────────────────────────
async function summarize(text, type) {
  const prompts = {
    short:    `Summarize this document in 3-4 sentences. Capture the main topic, key points, and conclusion.\n\nDocument:\n${text.slice(0,6000)}`,
    detailed: `Write a comprehensive summary including: main topic, key arguments, evidence, conclusions, and significance.\n\nDocument:\n${text.slice(0,8000)}`,
    bullets:  `Create a structured bullet-point summary:\n\n**📌 Main Topic:**\n• [topic]\n\n**🔑 Key Points:**\n• [points]\n\n**💡 Insights:**\n• [insights]\n\n**✅ Conclusion:**\n• [conclusion]\n\nDocument:\n${text.slice(0,7000)}`,
  };
  return call([
    { role: 'system', content: 'You are Saathi, an expert document analyst. Create clear, accurate summaries.' },
    { role: 'user',   content: prompts[type] || prompts.short }
  ], { temperature: 0.3, maxTokens: 1500 });
}

// ── Flashcards ────────────────────────────────────────────────
async function flashcards(text, count = 10) {
  const raw = await call([
    { role: 'system', content: `Generate exactly ${count} flashcards as a JSON array. Return ONLY valid JSON, no markdown, no explanation:\n[{"q":"...","a":"...","difficulty":"easy|medium|hard","topic":"..."}]` },
    { role: 'user',   content: `Generate ${count} flashcards from:\n\n${text.slice(0,8000)}` }
  ], { temperature: 0.5, maxTokens: 3000 });

  try {
    const match = raw.match(/\[[\s\S]*\]/);
    if (match) return JSON.parse(match[0]);
  } catch {}

  // Fallback parse
  const cards = [];
  const lines = raw.split('\n');
  let q = '';
  for (const line of lines) {
    if (line.match(/^Q[\d.):]/i)) q = line.replace(/^Q[\d.):]\s*/i,'').trim();
    else if (line.match(/^A[\d.):]/i) && q) {
      cards.push({ q, a: line.replace(/^A[\d.):]\s*/i,'').trim(), difficulty:'medium', topic:'General' });
      q = '';
    }
  }
  return cards.length ? cards : [{ q:'Could not parse flashcards', a: raw.slice(0,200), difficulty:'medium', topic:'Error' }];
}

// ── Podcast script ────────────────────────────────────────────
async function podcast(text, name = 'Document') {
  return call([
    {
      role: 'system',
      content: `
Create a natural, human-like teaching conversation based on the
provided document.

CHARACTERS:
- Maya: A patient, friendly teacher who explains concepts simply.
- Alex: A curious student who asks useful questions.

CONVERSATION RULES:
1. Start with a short, natural introduction of no more than 1–2 sentences.
2. Get directly into the topic. Do not announce a podcast title,
   host names, or give a long welcome.
3. Maya explains one concept at a time in simple language.
4. Alex asks natural questions when a concept needs clarification.
5. Maya answers with relatable examples and analogies.
6. Let the conversation flow naturally, like a real classroom.
7. Include short follow-up questions, reactions, and summaries
   only when they help learning.
8. Explain technical terms when they first appear.
9. Avoid repetitive phrases such as "Absolutely!", "Great question!"
   and "That's a great point!" in every exchange.
10. Cover the important information from the document accurately.
11. Do not invent facts or claim that the document says something
    it does not support.
12. Keep the conversation engaging without unnecessary filler.

OUTPUT FORMAT:
Maya: [Short introduction and explanation]
Alex: [A natural question]
Maya: [Clear explanation with an example]
Alex: [Follow-up question or observation]

Output only spoken dialogue, with each speaker turn on a new line.
Do not include titles, headings, timestamps, stage directions,
Markdown formatting, or production notes.

`
    },

    {
      role: 'user',
      content: `
Create a natural teacher-student conversation based ONLY on this document.

Document name: "${name}"

DOCUMENT:

${text.slice(0, 12000)}
`
    }
  ], {
    temperature: 0.85,
    maxTokens: 3500
  });
}
// ── Exam ──────────────────────────────────────────────────────
async function exam(text, count = 5) {
  const raw = await call([
    { role: 'system', content: `Generate ${count} exam questions as JSON array. Mix MCQ and short_answer. Return ONLY valid JSON:\n[{"type":"mcq","question":"...","options":["A) ...","B) ...","C) ...","D) ..."],"correct":"A","explanation":"..."},{"type":"short_answer","question":"...","model_answer":"..."}]` },
    { role: 'user',   content: `Generate ${count} exam questions from:\n\n${text.slice(0,6000)}` }
  ], { temperature: 0.4, maxTokens: 2500 });
  try {
    const match = raw.match(/\[[\s\S]*\]/);
    return match ? JSON.parse(match[0]) : [];
  } catch { return []; }
}

async function evalAnswer(question, userAnswer, modelAnswer) {
  const raw = await call([
    { role: 'system', content: 'Evaluate the student answer and return JSON: {"score":0-100,"feedback":"...","missed":["..."]}' },
    { role: 'user',   content: `Question: ${question}\nModel answer: ${modelAnswer}\nStudent answer: ${userAnswer}` }
  ], { temperature: 0.2, maxTokens: 500 });
  try {
    const match = raw.match(/\{[\s\S]*\}/);
    return match ? JSON.parse(match[0]) : { score: 0, feedback: raw };
  } catch { return { score: 0, feedback: raw }; }
}

// ── Compare docs ──────────────────────────────────────────────
async function compare(texts, names) {
  const docs = texts.map((t,i) => `=== ${names[i]} ===\n${t.slice(0,3000)}`).join('\n\n');
  return call([
    { role: 'system', content: 'You are a document analyst. Compare these documents with similarities, differences, and synthesis.' },
    { role: 'user',   content: `Compare:\n\n${docs}` }
  ], { temperature: 0.3, maxTokens: 2000 });
}

module.exports = { ragChat, summarize, flashcards, podcast, exam, evalAnswer, compare };

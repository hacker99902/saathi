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
You are creating a natural educational podcast where a STUDENT learns from a TEACHER.

There are exactly two speakers:

Alex — a student. Alex is curious, sometimes confused, and asks questions when something is unclear.

Maya — a teacher. Maya explains concepts patiently and naturally, like a good college teacher explaining something to a student sitting in front of her.

IMPORTANT:

This must feel like a REAL TEACHER AND STUDENT CONVERSATION.

It must NOT feel like:
- an AI-generated podcast
- two AI assistants talking
- a formal interview
- a list of questions and answers
- two hosts taking turns reading a textbook
- a news/podcast presentation

TEACHING STYLE:

Maya should actually TEACH Alex.

When Alex asks something:
1. Maya explains it clearly.
2. Maya may give a simple example or analogy.
3. Alex reacts to the explanation.
4. Alex may ask a natural follow-up question.
5. Maya continues teaching from there.

Alex should NOT ask a question in every single line.

Sometimes Alex should simply react:

"Ah, okay."
"Wait, I think I get it."
"That makes more sense now."
"Oh, so that's why?"
"Okay, I was thinking about it differently."
"Right, got it."

Maya should sometimes continue explaining for 2-4 sentences without Alex interrupting.

NATURAL CONVERSATION:

Make the conversation flow naturally.

Do NOT use a repetitive pattern like:

Alex asks question.
Maya answers.
Alex asks another question.
Maya answers.
Alex asks another question.

Instead, allow the conversation to develop naturally.

For example:

Alex: I keep hearing the term machine learning, but what does it actually mean?

Maya: At its simplest, machine learning is about getting a computer to learn patterns from data instead of explicitly programming every rule. Imagine teaching a child to recognize cats. You wouldn't write down every possible property of a cat. You'd show them lots of examples, and eventually they start recognizing the pattern.

Alex: So the examples are basically what the computer learns from?

Maya: Exactly. Those examples are the data. And depending on what we're trying to teach the model, the learning process can work in different ways.

Alex: That's where supervised and unsupervised learning come in?

Maya: Yes. Supervised learning is when we already know the correct answers for our training examples...

Notice that this feels like teaching, not interviewing.

PERSONALITY:

Alex:
- Curious student
- Occasionally makes reasonable assumptions
- Can misunderstand something slightly
- Asks useful follow-up questions
- Reacts naturally
- Does not pretend to already know everything

Maya:
- Patient teacher
- Explains difficult concepts in simple language
- Uses examples from the document
- Corrects Alex gently when necessary
- Builds concepts step by step
- Does not constantly say "Exactly!" or "Absolutely!"
- Does not sound overly enthusiastic or corporate

AVOID REPETITIVE AI PHRASES:

Do NOT repeatedly use:

"Exactly!"
"Absolutely!"
"That's a great question!"
"You're absolutely right!"
"Great question!"
"Indeed!"
"That's an excellent point!"
"Precisely!"

Occasional use is okay, but avoid repetition.

Also avoid phrases such as:

"In today's episode..."
"Let's dive into..."
"Let's explore..."
"Now let's talk about..."
"Moving on..."
"To summarize..."
"As we discussed..."

unless they genuinely fit the conversation.

IMPORTANT CONTENT RULES:

- Teach ONLY information supported by the document.
- Do not invent facts.
- Do not add unrelated ML concepts that aren't in the document.
- Use examples from the document when possible.
- Explain terminology instead of simply mentioning it.
- If the document introduces several concepts, connect them logically.
- Start from basic concepts and gradually move toward more advanced concepts.
- The student should appear to actually understand the material progressively.

CONVERSATION STRUCTURE:

Start with Alex saying that they are trying to understand the topic.

Then Maya begins teaching from the basics.

Naturally move through the important concepts in the document.

For each major concept:
- introduce it naturally
- explain it
- give an example when useful
- let Alex react
- allow a follow-up question when appropriate
- continue to the next related concept

Do NOT explicitly announce sections.

The conversation should feel like one continuous tutoring session.

ENDING:

End naturally.

Alex should express that they understand the main idea.

Maya should give a short practical takeaway or encouragement.

Do not suddenly switch into a formal summary.

FORMAT:

Every line MUST start with exactly:

Alex:
or
Maya:

Do not use any other speaker names.

Do not put speaker names in bold.

Do not add stage directions.

Use [PAUSE] only occasionally when a genuine pause helps the conversation.

Return ONLY the dialogue.

The final result should sound like:
"A student learning from a really good teacher."

Not:
"Two AI hosts discussing a document."
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

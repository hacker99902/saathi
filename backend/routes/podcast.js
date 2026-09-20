const router = require('express').Router();

const { podcast } = require('../services/groq');
const { extractText } = require('../services/docService');
const store = require('../utils/store');


/**
 * POST /api/podcast
 *
 * Generates an Alex + Maya educational podcast script
 * from an uploaded document.
 *
 * Browser speech synthesis is used on the frontend.
 * No audio is generated on the backend.
 */
router.post('/', async (req, res) => {

    const { docId } = req.body;

    // --------------------------------------------------
    // Validate request
    // --------------------------------------------------

    if (!docId) {
        return res.status(400).json({
            error: 'docId required'
        });
    }

    // --------------------------------------------------
    // Find document
    // --------------------------------------------------

    const doc = store.getDoc(docId);

    if (!doc) {
        return res.status(404).json({
            error: 'Document not found'
        });
    }

    try {

        console.log(`🎙️ Generating podcast for: ${doc.originalName}`);

        // --------------------------------------------------
        // Extract document text
        // --------------------------------------------------

        const { text } = await extractText(
            doc.filePath,
            doc.originalName
        );

        if (!text || !text.trim()) {
            return res.status(400).json({
                error: 'The document does not contain readable text.'
            });
        }

        console.log(
            `📖 Document text extracted: ${text.length} characters`
        );

        // --------------------------------------------------
        // Generate Alex + Maya conversation
        // --------------------------------------------------

        console.log(
            '🤖 Generating teacher-student conversation...'
        );

        const script = await podcast(
            text,
            doc.originalName
        );

        if (!script || !script.trim()) {
            return res.status(500).json({
                error: 'Failed to generate podcast script.'
            });
        }

        // --------------------------------------------------
        // Parse conversation
        // --------------------------------------------------

        const segments = parseScript(script);

        if (!segments.length) {

            console.warn(
                '⚠️ No valid Alex/Maya dialogue segments found.'
            );

            return res.status(500).json({
                error: 'Generated podcast did not contain valid Alex/Maya dialogue.'
            });
        }

        console.log(
            `📝 Generated ${segments.length} dialogue segments`
        );

        // --------------------------------------------------
        // Estimate duration
        // --------------------------------------------------

        const wordCount = segments.reduce(
            (total, segment) => {
                return total + segment.text.split(/\s+/).length;
            },
            0
        );

        // Browser TTS will normally speak somewhat slower
        // than a normal conversational reading.
        const estimatedDuration = Math.max(
            1,
            Math.ceil(wordCount / 140)
        );

        // --------------------------------------------------
        // Response
        // --------------------------------------------------

        return res.json({

            script,

            segments,

            docName: doc.originalName,

            estimatedDuration,

            wordCount,

            segmentCount: segments.length,

            tts: {
                engine: 'browser',
                type: 'speechSynthesis'
            }

        });

    } catch (error) {

        console.error(
            '❌ Podcast generation error:',
            error
        );

        return res.status(500).json({
            error: error.message || 'Failed to generate podcast.'
        });
    }
});


/**
 * Parse the generated Alex/Maya conversation.
 *
 * Expected format:
 *
 * Alex: ...
 * Maya: ...
 *
 * The parser also handles multiline dialogue:
 *
 * Maya: First sentence.
 * Second sentence.
 *
 * Alex: Response.
 */
function parseScript(script) {

    const lines = script
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .split('\n');

    const segments = [];

    let currentSpeaker = null;
    let currentText = [];


    function saveCurrentSegment() {

        if (!currentSpeaker || !currentText.length) {
            return;
        }

        const text = currentText
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();

        if (!text) {
            return;
        }

        segments.push({
            speaker: currentSpeaker,
            text: cleanSpeechText(text)
        });

        currentSpeaker = null;
        currentText = [];
    }


    for (const rawLine of lines) {

        const line = rawLine.trim();

        if (!line) {
            continue;
        }

        // ----------------------------------------------
        // Match speaker
        // ----------------------------------------------

        const match = line.match(
            /^(Alex|Maya)\s*:\s*(.*)$/i
        );

        if (match) {

            // Save previous speaker
            saveCurrentSegment();

            currentSpeaker =
                capitalizeSpeaker(match[1]);

            if (match[2]) {
                currentText.push(match[2]);
            }

            continue;
        }

        // ----------------------------------------------
        // Multiline continuation
        // ----------------------------------------------

        if (currentSpeaker) {

            currentText.push(line);

        }
    }

    // Save final segment
    saveCurrentSegment();


    // ----------------------------------------------
    // Validate speakers
    // ----------------------------------------------

    return segments.filter(segment => {

        return (
            (segment.speaker === 'Alex' ||
             segment.speaker === 'Maya') &&
            segment.text.length > 0
        );
    });
}


/**
 * Clean special instructions generated by the LLM.
 *
 * These instructions should not be spoken by the
 * browser TTS engine.
 */
function cleanSpeechText(text) {

    return text

        // Pause markers
        .replace(/\[PAUSE\]/gi, '...')

        // Emphasis markers
        .replace(/\[EMPHASIS\]/gi, '')

        // Other common stage directions
        .replace(/\[SILENCE\]/gi, '...')

        // Remove markdown bold
        .replace(/\*\*(.*?)\*\*/g, '$1')

        // Remove markdown italic
        .replace(/\*(.*?)\*/g, '$1')

        // Remove backticks
        .replace(/`([^`]+)`/g, '$1')

        // Remove speaker labels if the model
        // accidentally repeats them
        .replace(/^(Alex|Maya)\s*:\s*/i, '')

        // Normalize whitespace
        .replace(/\s+/g, ' ')

        .trim();
}


/**
 * Normalize speaker name.
 */
function capitalizeSpeaker(speaker) {

    const value = speaker
        .trim()
        .toLowerCase();

    if (value === 'alex') {
        return 'Alex';
    }

    if (value === 'maya') {
        return 'Maya';
    }

    return speaker;
}


module.exports = router;
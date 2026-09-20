/**
 * Saathi AI - ElevenLabs TTS Service
 * Converts podcast dialogue into natural speech.
 */

const { ElevenLabsClient } = require('@elevenlabs/elevenlabs-js');

const apiKey = process.env.ELEVENLABS_API_KEY;

if (!apiKey) {
  console.warn('⚠️ ELEVENLABS_API_KEY is not set');
}

const elevenlabs = new ElevenLabsClient({
  apiKey,
});

/*
 * We'll put the actual voice IDs here after
 * choosing the voices from ElevenLabs.
 */
const VOICES = {
  alex: 'AMje7XhK0v56ksuSOE5h',
  maya: 'acY43jPU6KjSJPnreYUt',
};

async function generateSpeech(text, speaker) {
  if (!text || !text.trim()) {
    throw new Error('Text is required for TTS');
  }

  const voiceId =
    speaker.toLowerCase() === 'maya'
      ? VOICES.maya
      : VOICES.alex;

  if (voiceId.startsWith('YOUR_')) {
    throw new Error(`Voice ID for ${speaker} has not been configured`);
  }

  const audio = await elevenlabs.textToSpeech.convert(voiceId, {
    text,
    modelId: 'eleven_v3',
    outputFormat: 'mp3_44100_128',
  });

  return audio;
}

module.exports = {
  generateSpeech,
  VOICES,
};
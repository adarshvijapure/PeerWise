/**
 * voice_recorder.js
 * -----------------
 * WebRTC / MediaRecorder voice note recording.
 * Exposes a global `initVoiceRecorder(config)` function used by templates.
 *
 * Config object keys:
 *   recordBtnId, stopBtnId, discardBtnId
 *   statusId, timerId
 *   playbackAreaId, previewId
 *   fileInputId
 */

function initVoiceRecorder(cfg) {
  const recordBtn    = document.getElementById(cfg.recordBtnId);
  const stopBtn      = document.getElementById(cfg.stopBtnId);
  const discardBtn   = document.getElementById(cfg.discardBtnId);
  const statusEl     = document.getElementById(cfg.statusId);
  const timerEl      = document.getElementById(cfg.timerId);
  const playbackArea = document.getElementById(cfg.playbackAreaId);
  const preview      = document.getElementById(cfg.previewId);
  const fileInput    = document.getElementById(cfg.fileInputId);

  if (!recordBtn) return;  // element not on this page

  let mediaRecorder = null;
  let audioChunks   = [];
  let timerInterval = null;
  let secondsElapsed = 0;

  function formatTime(s) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  }

  function startTimer() {
    secondsElapsed = 0;
    timerEl.textContent = '0:00';
    timerInterval = setInterval(() => {
      secondsElapsed++;
      timerEl.textContent = formatTime(secondsElapsed);
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerInterval);
  }

  recordBtn.addEventListener('click', async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];

      const options = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? { mimeType: 'audio/webm;codecs=opus' }
        : {};

      mediaRecorder = new MediaRecorder(stream, options);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        stopTimer();

        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunks, { type: mimeType });
        const url  = URL.createObjectURL(blob);

        preview.src = url;
        statusEl.classList.add('hidden');
        playbackArea.classList.remove('hidden');

        // Attach blob to the hidden file input as a File object
        const ext  = mimeType.includes('ogg') ? 'ogg' : 'webm';
        const file = new File([blob], `voice_note_${Date.now()}.${ext}`, { type: mimeType });
        const dt   = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
      };

      mediaRecorder.start(250);  // collect every 250ms
      recordBtn.classList.add('hidden');
      statusEl.classList.remove('hidden');
      startTimer();

    } catch (err) {
      console.error('Microphone access denied:', err);
      alert('Could not access microphone. Please allow microphone permission and try again.');
    }
  });

  stopBtn.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  });

  discardBtn.addEventListener('click', () => {
    preview.src = '';
    fileInput.value = '';
    playbackArea.classList.add('hidden');
    recordBtn.classList.remove('hidden');
  });
}

// Auto-init for the primary query creation recorder
document.addEventListener('DOMContentLoaded', () => {
  // Primary recorder on the create-query page
  initVoiceRecorder({
    recordBtnId:    'record-btn',
    stopBtnId:      'stop-btn',
    discardBtnId:   'discard-btn',
    statusId:       'recording-status',
    timerId:        'record-timer',
    playbackAreaId: 'playback-area',
    previewId:      'voice-preview',
    fileInputId:    'voice_note',
  });
});

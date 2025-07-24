const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

let ffmpegProcess = null;
let currentUrl = null;
let restartTimeout = null;
let isReady = false;

const hlsFolder = path.join(__dirname, 'public', 'stream');

function clearHlsFolder() {
  if (fs.existsSync(hlsFolder)) {
    fs.readdirSync(hlsFolder).forEach(file => {
      try {
        fs.unlinkSync(path.join(hlsFolder, file));
      } catch (e) {
        console.error('Erro ao apagar arquivo:', file, e);
      }
    });
  } else {
    fs.mkdirSync(hlsFolder, { recursive: true });
  }
}

function startFfmpeg(url) {
  clearHlsFolder();
  isReady = false;

  console.log('Iniciando FFmpeg com URL:', url);
  ffmpegProcess = spawn('ffmpeg', [
    '-reconnect', '1',
    '-reconnect_streamed', '1',
    '-reconnect_delay_max', '10',
    '-i', url,
    '-c:v', 'copy',
    '-c:a', 'aac',
    '-f', 'hls',
    '-hls_time', '4',
    '-hls_list_size', '6',
    '-hls_flags', 'delete_segments',
    path.join(hlsFolder, 'index.m3u8')
  ]);

  ffmpegProcess.stderr.on('data', data => {
    const str = data.toString();
    if (str.includes('Opening') && str.includes('index.m3u8.tmp')) {
      if (!isReady) {
        isReady = true;
        console.log('Stream HLS local pronto para playback!');
      }
    }
    process.stderr.write(data);
  });

  ffmpegProcess.on('exit', (code, signal) => {
    console.log(`FFmpeg saiu com código ${code}, sinal ${signal}`);
    ffmpegProcess = null;
    isReady = false;
    if (currentUrl) {
      console.log('Reiniciando restream em 5 segundos...');
      restartTimeout = setTimeout(() => {
        startFfmpeg(currentUrl);
      }, 5000);
    }
  });
}

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.post('/restream', (req, res) => {
  const inputUrl = req.body.inputUrl;

  if (
    !inputUrl ||
    !inputUrl.startsWith('http') ||
    (!inputUrl.endsWith('.m3u8') && !inputUrl.endsWith('.ts'))
  ) {
    return res.send(`
      <p>URL inválida! Deve começar com http e terminar com .m3u8 ou .ts</p>
      <a href="/">Voltar</a>
    `);
  }

  if (restartTimeout) {
    clearTimeout(restartTimeout);
    restartTimeout = null;
  }

  if (ffmpegProcess) {
    ffmpegProcess.kill('SIGKILL');
    ffmpegProcess = null;
  }

  currentUrl = inputUrl;
  startFfmpeg(inputUrl);

  const streamUrl = `/stream/index.m3u8`;

  res.send(`
    <h2>Reestream iniciado!</h2>
    <p>Link original: <a href="${inputUrl}" target="_blank">${inputUrl}</a></p>
    <p>Link alternativo (local): <a href="${streamUrl}" target="_blank">${streamUrl}</a></p>
    <video src="${streamUrl}" controls autoplay style="width: 600px; height: 340px;"></video>
    <br><br>
    <a href="/">Voltar</a>
  `);
});

app.get('/status', (req, res) => {
  res.json({
    streaming: ffmpegProcess !== null,
    url: currentUrl,
    ready: isReady
  });
});

app.listen(PORT, () => {
  console.log(`Servidor rodando em http://localhost:${PORT}`);
});

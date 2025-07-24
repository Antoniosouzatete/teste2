const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const cors = require('cors');

const app = express();
const port = process.env.PORT || 3000;
const ffmpegPath = process.platform === 'win32' ? 'C:\\ffmpeg\\bin\\ffmpeg.exe' : 'ffmpeg';
const streamDir = path.join(__dirname, 'streams');

app.use(cors());
app.use(express.json());
app.use(express.static('public'));
app.use('/stream', express.static(streamDir));

// Cria pasta "streams" se não existir
if (!fs.existsSync(streamDir)) {
  fs.mkdirSync(streamDir);
}

// Armazena streams ativos
const activeStreams = {};

// Gera nome do arquivo baseado na URL
function generateStreamName(url) {
  return Buffer.from(url).toString('base64').replace(/=/g, '');
}

// Inicia restream
app.post('/start', (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: 'URL obrigatória' });

  const name = generateStreamName(url);
  const outputPath = path.join(streamDir, `${name}.m3u8`);
  const outputUrl = `${req.protocol}://${req.get('host')}/stream/${name}.m3u8`;

  // Se já estiver rodando
  if (activeStreams[name]) {
    return res.json({ message: 'Já em execução', url: outputUrl });
  }

  const ffmpeg = spawn(ffmpegPath, [
    '-i', url,
    '-c:v', 'copy',
    '-c:a', 'aac',
    '-f', 'hls',
    '-hls_time', '4',
    '-hls_list_size', '5',
    '-hls_flags', 'delete_segments',
    outputPath
  ]);

  ffmpeg.stderr.on('data', data => {
    console.log(`[FFmpeg ${name}] ${data}`);
  });

  ffmpeg.on('close', code => {
    console.log(`FFmpeg encerrado para ${name} com código ${code}`);
    delete activeStreams[name];
  });

  activeStreams[name] = ffmpeg;

  res.json({ message: 'Restream iniciado', url: outputUrl });
});

app.listen(port, () => {
  console.log(`Servidor rodando em http://localhost:${port}`);
});

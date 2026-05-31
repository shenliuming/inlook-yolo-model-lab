const packForm = document.getElementById('pack-form');
const reburnForm = document.getElementById('reburn-form');
const logs = document.getElementById('logs');
const downloads = document.getElementById('downloads');

const renderLogs = (items) => {
  logs.textContent = Array.isArray(items) && items.length ? items.join('\n') : '等待开始…';
};

const renderDownloads = (payload) => {
  const links = [];
  if (payload?.downloads?.mp4) links.push(['下载 MP4', payload.downloads.mp4]);
  if (payload?.downloads?.srt) links.push(['下载 SRT', payload.downloads.srt]);
  if (payload?.downloads?.ass) links.push(['下载 ASS', payload.downloads.ass]);
  if (payload?.downloads?.txt) links.push(['下载 TXT', payload.downloads.txt]);

  if (!links.length) {
    downloads.innerHTML = '<span class="placeholder">生成完成后会显示下载链接。</span>';
    return;
  }

  downloads.innerHTML = links
    .map(([label, href]) => `<a class="download-link" href="${href}" target="_blank" rel="noreferrer">${label}</a>`)
    .join('');
};

const request = async (url, formData) => {
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || '请求失败');
  }
  return payload;
};

packForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  renderLogs(['[INFO] 正在处理，请稍等…']);
  downloads.innerHTML = '<span class="placeholder">正在生成结果…</span>';

  const formData = new FormData(packForm);
  try {
    const payload = await request('/api/subtitle-pack', formData);
    reburnForm.elements.job_id.value = payload.job_id;
    renderLogs(payload.logs);
    renderDownloads(payload);
  } catch (error) {
    renderLogs([`[ERROR] ${error.message}`]);
    downloads.innerHTML = '<span class="placeholder">生成失败，请查看日志。</span>';
  }
});

reburnForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const jobId = reburnForm.elements.job_id.value;
  if (!jobId) {
    renderLogs(['[WARN] 请先生成一次字幕，再重新导出。']);
    return;
  }

  renderLogs(['[INFO] 正在重新烧录字幕…']);
  const formData = new FormData(reburnForm);
  try {
    const payload = await request('/api/reburn', formData);
    renderLogs(payload.logs);
    renderDownloads(payload);
  } catch (error) {
    renderLogs([`[ERROR] ${error.message}`]);
  }
});

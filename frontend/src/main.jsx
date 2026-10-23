import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import { Upload, Play, Pause, Download, Sparkles, SlidersHorizontal, RefreshCw, Wand2 } from 'lucide-react'
import './styles.css'

const API = 'http://127.0.0.1:8000'

const styles = {
  short: { name: '短视频紧凑', silenceMs: 90, silenceDb: -40, note: '更敏感识别短停顿，补出短视频口播的利落节奏' },
  natural: { name: '自然口播', silenceMs: 180, silenceDb: -35, note: '先自动把过短停顿补到自然口播节奏' },
  slow: { name: '慢速旁白', silenceMs: 180, silenceDb: -35, note: '先自动明显加长句尾和段落停顿，更像旁白' }
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return '00:00.000'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 1000)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
}

function App() {
  const waveformRef = useRef(null)
  const wavesurferRef = useRef(null)
  const regionsRef = useRef(null)
  const [audioUrl, setAudioUrl] = useState('')
  const [audioName, setAudioName] = useState('')
  const [audioPath, setAudioPath] = useState('')
  const [styleKey, setStyleKey] = useState('natural')
  const [pauses, setPauses] = useState([])
  const [result, setResult] = useState(null)
  const [activeId, setActiveId] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [busy, setBusy] = useState(false)
  const [bulkScale, setBulkScale] = useState(100)
  const [status, setStatus] = useState('上传音频后，点击“识别并优化停顿”。')

  useEffect(() => {
    if (!waveformRef.current) return
    const regions = RegionsPlugin.create()
    regionsRef.current = regions
    const ws = WaveSurfer.create({
      container: waveformRef.current,
      height: 150,
      waveColor: '#64748b',
      progressColor: '#a78bfa',
      cursorColor: '#f97316',
      barWidth: 2,
      barGap: 1,
      normalize: true,
      plugins: [regions]
    })
    wavesurferRef.current = ws
    ws.on('play', () => setPlaying(true))
    ws.on('pause', () => setPlaying(false))
    ws.on('finish', () => setPlaying(false))
    return () => ws.destroy()
  }, [])

  useEffect(() => {
    if (!audioUrl || !wavesurferRef.current) return
    wavesurferRef.current.load(audioUrl)
  }, [audioUrl])

  useEffect(() => {
    if (!regionsRef.current) return
    regionsRef.current.clearRegions()
    pauses.forEach(pause => {
      regionsRef.current.addRegion({
        id: String(pause.id),
        start: pause.start,
        end: pause.end,
        color: pause.id === activeId ? 'rgba(249, 115, 22, 0.35)' : 'rgba(124, 58, 237, 0.22)',
        drag: false,
        resize: false
      })
    })
  }, [pauses, activeId])

  async function handleAudio(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setBusy(true)
    setStatus('正在上传到本地后端，不会上传云端...')
    setAudioUrl(URL.createObjectURL(file))
    setAudioName(file.name)
    setPauses([])
    setResult(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const response = await fetch(`${API}/upload`, { method: 'POST', body: form })
      const data = await response.json()
      setAudioPath(data.audio_path)
      setStatus('音频已就绪。点击“识别并优化停顿”。')
    } catch (error) {
      setStatus('上传失败：请确认后端服务已启动。')
    } finally {
      setBusy(false)
    }
  }

  async function analyzePauses() {
    if (!audioPath) return setStatus('请先上传音频。')
    const style = styles[styleKey]
    setBusy(true)
    setResult(null)
    setStatus('正在识别所有停顿，并自动生成一版优化后的完整音频...')
    try {
      const response = await fetch(`${API}/analyze-pauses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_path: audioPath, style: styleKey, silence_ms: style.silenceMs, silence_db: style.silenceDb })
      })
      const data = await response.json()
      if (!data.ok) throw new Error(data.message || '识别失败')
      setPauses(data.pauses.map(p => ({ ...p, suggested_duration: p.target_duration })))
      setBulkScale(100)
      setResult(data)
      setActiveId(data.pauses[0]?.id || null)
      setStatus(`已自动优化 ${data.pauses.length} 个停顿，并生成完整音频。请先试听自动版；不满意的地方再微调后重新导出。`)
    } catch (error) {
      setStatus(`识别失败：${error.message}`)
    } finally {
      setBusy(false)
    }
  }

  async function renderAudio() {
    if (!audioPath || pauses.length === 0) return setStatus('请先识别停顿。')
    setBusy(true)
    setStatus('正在按当前停顿设置重新生成完整音频...')
    try {
      const response = await fetch(`${API}/render-pauses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_path: audioPath, pauses })
      })
      const data = await response.json()
      if (!data.ok) throw new Error(data.message || '导出失败')
      setResult(data)
      setStatus(`已导出完整音频：${data.output_dir}`)
    } catch (error) {
      setStatus(`导出失败：${error.message}`)
    } finally {
      setBusy(false)
    }
  }

  function updatePause(id, value) {
    const target = Number(value)
    setPauses(items => items.map(p => p.id === id ? { ...p, target_duration: target, action: target > p.original_duration + 0.03 ? '加长' : target < p.original_duration - 0.03 ? '缩短' : '保留' } : p))
  }

  function resetPause(id) {
    setPauses(items => items.map(p => p.id === id ? { ...p, target_duration: p.suggested_duration || p.original_duration, action: (p.suggested_duration || p.original_duration) > p.original_duration + 0.03 ? '加长' : '保留' } : p))
  }

  function applyBulkScale(scale) {
    setBulkScale(scale)
    const factor = scale / 100
    setPauses(items => items.map(p => {
      const base = Number(p.suggested_duration || p.target_duration || p.original_duration)
      const target = Math.max(0.05, Math.min(3, Number((base * factor).toFixed(2))))
      return { ...p, target_duration: target, action: target > p.original_duration + 0.03 ? '加长' : target < p.original_duration - 0.03 ? '缩短' : '保留' }
    }))
  }

  function addAllPauses(delta) {
    setBulkScale(100)
    setPauses(items => items.map(p => {
      const target = Math.max(0.05, Math.min(3, Number((Number(p.target_duration) + delta).toFixed(2))))
      return { ...p, target_duration: target, action: target > p.original_duration + 0.03 ? '加长' : target < p.original_duration - 0.03 ? '缩短' : '保留' }
    }))
  }

  function resetAllToSuggested() {
    setBulkScale(100)
    setPauses(items => items.map(p => {
      const target = Number(p.suggested_duration || p.original_duration)
      return { ...p, target_duration: target, action: target > p.original_duration + 0.03 ? '加长' : target < p.original_duration - 0.03 ? '缩短' : '保留' }
    }))
  }

  function playAround(pause) {
    if (!wavesurferRef.current) return
    setActiveId(pause.id)
    wavesurferRef.current.play(Math.max(0, pause.start - 1.2), pause.end + 1.2)
  }

  function togglePlay() {
    if (!wavesurferRef.current) return
    wavesurferRef.current.playPause()
  }

  const totalBefore = pauses.reduce((sum, p) => sum + p.original_duration, 0)
  const totalAfter = pauses.reduce((sum, p) => sum + Number(p.target_duration || 0), 0)

  return <main className="app">
    <section className="hero">
      <div>
        <p className="eyebrow">本地停顿重塑工具</p>
        <h1>口播停顿重塑器</h1>
        <p className="sub">上传完整音频，我先自动加长过短停顿并生成完整音频；你只复审少量不满意的地方。</p>
      </div>
      <div className="heroCard"><Sparkles size={18} /><span>本地处理，不上传云端</span></div>
    </section>

    <section className="statusBar">{busy ? '处理中：' : '状态：'}{status}</section>

    <section className="grid two">
      <div className="panel">
        <div className="panelTitle"><Upload size={18} /> 导入完整音频</div>
        <label className="dropzone">
          <input type="file" accept="audio/*" onChange={handleAudio} disabled={busy} />
          <span>{audioName || '选择 mp3 / wav / m4a 音频'}</span>
        </label>
      </div>
      <div className="panel">
        <div className="panelTitle"><SlidersHorizontal size={18} /> 停顿风格</div>
        <div className="presetGroup bigButtons">
          {Object.entries(styles).map(([key, item]) => <button key={key} className={styleKey === key ? 'active' : ''} onClick={() => setStyleKey(key)} disabled={busy}>{item.name}</button>)}
        </div>
        <p className="hint">{styles[styleKey].note}</p>
      </div>
    </section>

    <section className="panel waveformPanel">
      <div className="toolbar">
        <div className="panelTitle">波形和停顿位置</div>
        <div className="actions">
          <button onClick={togglePlay} disabled={!audioUrl || busy}>{playing ? <Pause size={16} /> : <Play size={16} />} 播放</button>
          <button className="primary" onClick={analyzePauses} disabled={!audioPath || busy}><Wand2 size={16} /> 自动优化并生成音频</button>
          <button onClick={renderAudio} disabled={!pauses.length || busy}><Download size={16} /> 微调后重新导出</button>
        </div>
      </div>
      <div ref={waveformRef} className="waveform" />
      <div className="summaryCards">
        <div>识别停顿 <strong>{pauses.length}</strong> 个</div>
        <div>原总停顿 <strong>{totalBefore.toFixed(2)}s</strong></div>
        <div>新总停顿 <strong>{totalAfter.toFixed(2)}s</strong></div>
      </div>
    </section>

    <section className="grid two bottomGrid">
      <div className="panel">
        <div className="panelTitle">复审区：只微调不满意的停顿</div>
        {pauses.length > 0 && <div className="bulkPanel">
          <div className="bulkHeader">
            <strong>一键批量调节所有停顿</strong>
            <span>{bulkScale}%</span>
          </div>
          <input type="range" min="60" max="180" step="5" value={bulkScale} onChange={e => applyBulkScale(Number(e.target.value))} />
          <div className="bulkActions">
            <button onClick={() => applyBulkScale(85)}>整体更紧凑</button>
            <button onClick={() => applyBulkScale(120)}>整体更慢一点</button>
            <button onClick={() => addAllPauses(0.1)}>全部 +0.1s</button>
            <button onClick={() => addAllPauses(-0.1)}>全部 -0.1s</button>
            <button onClick={resetAllToSuggested}>恢复自动建议</button>
          </div>
        </div>}
        <div className="segmentList pauseList">
          {pauses.length === 0 && <div className="empty">点击“自动优化并生成音频”后，这里会列出系统已经调好的停顿。</div>}
          {pauses.map(pause => <div className={activeId === pause.id ? 'pauseItem activeSegment' : 'pauseItem'} key={pause.id}>
            <div className="pauseHeader">
              <strong>停顿 {String(pause.id).padStart(2, '0')} · {pause.kind}</strong>
              <span>{pause.action}</span>
            </div>
            <div className="pauseMeta">位置 {formatTime(pause.position)} · 原 {pause.original_duration.toFixed(2)}s → 新 {Number(pause.target_duration).toFixed(2)}s</div>
            <input type="range" min="0.05" max="3" step="0.05" value={pause.target_duration} onChange={e => updatePause(pause.id, e.target.value)} />
            <div className="pauseActions">
              <button onClick={() => playAround(pause)}><Play size={14} /> 试听前后</button>
              <button onClick={() => resetPause(pause.id)}><RefreshCw size={14} /> 还原</button>
            </div>
          </div>)}
        </div>
      </div>
      <div className="panel">
        <div className="panelTitle"><Download size={18} /> 最终导出</div>
        {!result && <p className="hint">点击“自动优化并生成音频”后，会直接生成 edited_voice.wav。</p>}
        {result && <div className="exportBox">
          <div className="previewPlayer">
            <strong>在线试听优化后的音频</strong>
            <audio controls src={`${API}${result.download_url}`}></audio>
            <span>满意后再点击下方按钮自主下载。</span>
          </div>
          <a className="downloadBtn" href={`${API}${result.download_url}`} target="_blank">下载 edited_voice.wav</a>
          <a className="downloadBtn" href={`${API}${result.download_base}/pause_plan.json`} target="_blank">下载 pause_plan.json</a>
          <div className="outputPath">{result.output_dir}</div>
        </div>}
      </div>
    </section>
  </main>
}

createRoot(document.getElementById('root')).render(<App />)

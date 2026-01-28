import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { io } from 'socket.io-client';
import {
  Settings,
  Files,
  Activity,
  Upload,
  Trash2,
  Save,
  RefreshCw,
  Database,
  Volume2,
  Mic,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Zap,
  Terminal,
  MessageSquare,
  Activity as StatusIcon
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = "http://localhost:8080";
const ORCHESTRATOR_SOCKET = "http://localhost:5000"; // Puerto por defecto del SocketIO del orquestador

function App() {
  const [activeTab, setActiveTab] = useState('status');
  const [files, setFiles] = useState([]);
  const [voices, setVoices] = useState([]);
  const [config, setConfig] = useState({});
  const [health, setHealth] = useState({});
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [testing, setTesting] = useState(null);

  // Estados en tiempo real del orquestador
  const [orchState, setOrchState] = useState('OFFLINE');
  const [logs, setLogs] = useState([]);
  const [lastTranscript, setLastTranscript] = useState("");
  const [lastResponse, setLastResponse] = useState("");
  const [audioEnergy, setAudioEnergy] = useState(0);

  // Debug State
  const [debugText, setDebugText] = useState("");

  const socketRef = useRef();

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchHealth, 5000);

    // Conexión SocketIO
    socketRef.current = io(ORCHESTRATOR_SOCKET);

    socketRef.current.on('connect', () => {
      setOrchState('CONNECTED');
      addLog("Conectado al Orquestador");
    });

    socketRef.current.on('disconnect', () => {
      setOrchState('OFFLINE');
      addLog("Desconectado del Orquestador");
    });

    socketRef.current.on('audio_chunk', (data) => {
      // Normalizamos la energía para visualización (0-100 aprox)
      // Ajustar factor según sensibilidad
      const level = Math.min(100, (data.energy / 50));
      setAudioEnergy(level);
    });

    socketRef.current.on('state_changed', (data) => {
      setOrchState(data.to);
      addLog(`Estado: ${data.from} -> ${data.to}`);
    });

    socketRef.current.on('transcription_final', (data) => {
      setLastTranscript(data.text);
      addLog(`Usuario: ${data.text}`);
    });

    socketRef.current.on('rag_response', (data) => {
      setLastResponse(data.answer);
      addLog(`AI: ${data.answer}`);
    });

    return () => {
      clearInterval(interval);
      socketRef.current.disconnect();
    };
  }, []);

  const addLog = (msg) => {
    const time = new Date().toLocaleTimeString();
    setLogs(prev => [{ time, msg }, ...prev].slice(0, 50));
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [filesRes, configRes, voicesRes] = await Promise.all([
        axios.get(`${API_BASE}/files`),
        axios.get(`${API_BASE}/config`),
        axios.get(`${API_BASE}/voices`)
      ]);
      setFiles(filesRes.data);
      setConfig(configRes.data);
      setVoices(voicesRes.data);
      fetchHealth();
    } catch (err) {
      showMsg("Backend de gestión no disponible", "error");
    }
    setLoading(false);
  };

  const fetchHealth = async () => {
    try {
      const res = await axios.get(`${API_BASE}/health`);
      setHealth(res.data);
    } catch (err) { }
  };

  const showMsg = (text, type = "success") => {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 3000);
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      await axios.post(`${API_BASE}/files/upload`, formData);
      showMsg("Archivo subido!");
      fetchData();
    } catch (err) {
      showMsg("Fallo al subir archivo", "error");
    }
  };

  const deleteFile = async (name) => {
    try {
      await axios.delete(`${API_BASE}/files/${name}`);
      showMsg("Archivo eliminado");
      fetchData();
    } catch (err) {
      showMsg("Error al eliminar", "error");
    }
  };

  const updateConfig = async (key, value) => {
    try {
      await axios.post(`${API_BASE}/config?key=${key}&value=${value}`);
      setConfig({ ...config, [key]: value });
      showMsg("Guardado en .env");
    } catch (err) {
      showMsg("Error al guardar", "error");
    }
  };

  const handleVoiceUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.wav')) {
      showMsg("Solo se permiten archivos .wav", "error");
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    try {
      await axios.post(`${API_BASE}/voices/upload`, formData);
      showMsg("Voz subida correctamente");
      const voicesRes = await axios.get(`${API_BASE}/voices`);
      setVoices(voicesRes.data);
      if (voicesRes.data.length === 1) {
        updateConfig("TTS_VOICE_FILE", voicesRes.data[0].name);
      }
    } catch (err) {
      showMsg("Error al subir voz", "error");
    }
  };

  const deleteVoice = async (name) => {
    try {
      await axios.delete(`${API_BASE}/voices/${name}`);
      showMsg("Voz eliminada");
      const voicesRes = await axios.get(`${API_BASE}/voices`);
      setVoices(voicesRes.data);
      if (config.TTS_VOICE_FILE === name) {
        updateConfig("TTS_VOICE_FILE", voicesRes.data.length > 0 ? voicesRes.data[0].name : "");
      }
    } catch (err) {
      showMsg("Error al eliminar voz", "error");
    }
  };

  const handlePurge = async () => {
    if (window.confirm("¿ESTAS SEGURO? Esto borrará TODA la memoria del cerebro RAG. Esta acción no se puede deshacer.")) {
      try {
        await axios.delete(`${API_BASE}/rag/purge`);
        showMsg("Memoria purgada correctamente");
        fetchData();
      } catch (err) {
        showMsg("Error al purgar memoria", "error");
      }
    }
  };

  const runTest = async (module) => {
    setTesting(module);

    if (module === 'audio') {
      // Test de Audio especial (Client-side verification of socket events)
      const initialEnergy = audioEnergy;
      let maxDetected = 0;

      const checkAudio = new Promise((resolve) => {
        const start = Date.now();
        const checker = setInterval(() => {
          if (audioEnergy > maxDetected) maxDetected = audioEnergy;

          // Si detectamos energía significativa > 10%
          if (maxDetected > 10) {
            clearInterval(checker);
            resolve({ status: 'success', message: 'Micrófono detectando audio correctamente.' });
          }

          // Timeout de 5 segundos
          if (Date.now() - start > 5000) {
            clearInterval(checker);
            resolve({ status: 'error', message: 'No se detectó audio. Verifique su micrófono.' });
          }
        }, 100);
      });

      const res = await checkAudio;
      setTestResults(prev => ({ ...prev, [module]: res }));
      if (res.status === 'success') showMsg("Prueba de Audio exitosa");
      else showMsg("Fallo en prueba de Audio", "error");

      setTesting(null);
      return;
    }

    try {
      const res = await axios.get(`${API_BASE}/test/${module}`);
      setTestResults(prev => ({ ...prev, [module]: res.data }));
      if (res.data.status === 'success') {
        showMsg(`Prueba de ${module.toUpperCase()} exitosa`);
      } else {
        showMsg(`Fallo en prueba de ${module.toUpperCase()}`, "error");
      }
    } catch (err) {
      showMsg("Error al ejecutar prueba", "error");
    }
    setTesting(null);
  };

  const handleRestart = async () => {
    if (window.confirm("¿Seguro que quieres reiniciar el sistema? Esto desconectará el dashboard temporalmente.")) {
      try {
        await axios.post(`${API_BASE}/system/restart`);
      } catch (err) {
        // Es normal que falle la conexión al morir el proceso
        showMsg("Reiniciando sistema...");
      }
    }
  };

  const handleDebugAction = (action) => {
    if (!socketRef.current) return;

    switch (action) {
      case 'listen':
        socketRef.current.emit('manual_listen', {});
        showMsg("Escucha manual activada");
        break;
      case 'chat':
        if (!debugText) return;
        socketRef.current.emit('process_text', { text: debugText });
        showMsg(`Enviado al chat: ${debugText}`);
        break;
      case 'tts':
        if (!debugText) return;
        socketRef.current.emit('speak_text', { text: debugText });
        showMsg("Enviado a TTS");
        break;
      case 'rag':
        if (!debugText) return;
        socketRef.current.emit('query_rag', { text: debugText });
        showMsg("Consultando RAG...");
        break;
    }
  };

  return (
    <div className="min-h-screen p-8 max-w-6xl mx-auto">
      {/* Header */}
      <header className="flex justify-between items-center mb-12">
        <div>
          <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
            Voice Orchestrator
          </h1>
          <p className="text-gray-400 mt-2">Panel de Control y Gestión Centralizada</p>
        </div>
        <div className="flex gap-4">
          {Object.entries(health).map(([svc, status]) => (
            <div key={svc} className="flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-sm">
              <div className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-green-500 shadow-[0_0_8px_#22c55e]' :
                status === 'offline' ? 'bg-red-500' : 'bg-yellow-500'
                }`} />
              <span className="capitalize text-gray-300">{svc}</span>
            </div>
          ))}
        </div>
      </header>

      {/* Tabs */}
      <nav className="flex gap-2 p-1 glass rounded-xl mb-8 w-fit">
        {[
          { id: 'status', icon: StatusIcon, label: 'Estado' },
          { id: 'rag', icon: Database, label: 'Base de Datos (RAG)' },
          { id: 'config', icon: Settings, label: 'Configuración' },
          { id: 'tests', icon: Cpu, label: 'Pruebas' },
          { id: 'debug', icon: Terminal, label: 'Consola / Debug' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-6 py-2 rounded-lg transition-all ${activeTab === tab.id ? 'bg-blue-500 text-white shadow-lg' : 'hover:bg-white/5 text-gray-400'
              }`}
          >
            <tab.icon size={18} />
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Main Content */}
      <main className="grid grid-cols-1 gap-8">
        <AnimatePresence mode="wait">
          {activeTab === 'status' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid grid-cols-1 md:grid-cols-3 gap-6"
            >
              {/* Orquestador Realtime State */}
              <div className="glass-card md:col-span-1">
                <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <Zap size={20} className="text-yellow-400" /> Motor de Voz
                </h3>
                <div className="flex flex-col items-center justify-center py-8">
                  <div className={`text-6xl mb-4 font-black tracking-tighter ${orchState === 'OFFLINE' ? 'text-gray-700' : 'text-blue-500'
                    }`}>
                    {orchState}
                  </div>
                  <p className="text-gray-500 text-sm">Estado actual del flujo de IA</p>

                  {/* Visualizador de Micrófono */}
                  <div className="mt-6 w-full px-8 flex flex-col items-center">
                    <div className="flex items-center gap-2 mb-2">
                      <Mic size={16} className={audioEnergy > 5 ? "text-green-400" : "text-gray-600"} />
                      <span className="text-xs text-gray-500 uppercase font-bold">Nivel Micrófono</span>
                    </div>
                    <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-green-500 to-emerald-400"
                        animate={{ width: `${audioEnergy}%` }}
                        transition={{ type: "tween", ease: "linear", duration: 0.05 }}
                      />
                    </div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-white/5 space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 uppercase tracking-wider font-bold text-[10px]">STT (Whisper)</span>
                    <span className={health.stt === 'online' ? 'text-green-500' : 'text-red-500'}>{health.stt || 'pending'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 uppercase tracking-wider font-bold text-[10px]">TTS (XTTS)</span>
                    <span className={health.tts === 'online' ? 'text-green-500' : 'text-red-500'}>{health.tts || 'pending'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 uppercase tracking-wider font-bold text-[10px]">RAG Engine</span>
                    <span className={health.rag === 'online' ? 'text-green-500' : 'text-red-500'}>{health.rag || 'pending'}</span>
                  </div>
                </div>
              </div>

              {/* Live Chat View */}
              <div className="glass-card md:col-span-2">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <MessageSquare size={20} className="text-blue-400" /> Conversación Activa
                </h3>
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-white/5 border border-white/5 min-h-[80px]">
                    <span className="text-[10px] text-blue-400 font-bold uppercase block mb-1">Último que escuché</span>
                    <p className="text-lg text-gray-200">{lastTranscript || "Esperando voz..."}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-purple-500/5 border border-purple-500/10 min-h-[80px]">
                    <span className="text-[10px] text-purple-400 font-bold uppercase block mb-1">Respuesta del Robot</span>
                    <p className="text-lg text-purple-100">{lastResponse || "Sin respuesta todavía"}</p>
                  </div>
                </div>

                <h3 className="text-lg font-semibold mt-8 mb-4 flex items-center gap-2">
                  <Terminal size={20} className="text-gray-400" /> Eventos del Sistema
                </h3>
                <div className="bg-black/40 rounded-xl p-4 font-mono text-xs overflow-y-auto h-[160px] border border-white/5">
                  {logs.map((log, i) => (
                    <div key={i} className="mb-1">
                      <span className="text-gray-600 mr-2">[{log.time}]</span>
                      <span className="text-gray-300">{log.msg}</span>
                    </div>
                  ))}
                  {logs.length === 0 && <span className="text-gray-700 italic">Iniciando monitor de eventos...</span>}
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'tests' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-8"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  { id: 'stt', label: 'Speech-to-Text', desc: 'Valida carga de modelos Whisper y latencia de red.', icon: Mic },
                  { id: 'tts', label: 'Text-to-Speech', desc: 'Verifica generación de audio y salud de XTTS.', icon: Volume2 },
                  { id: 'rag', label: 'RAG Engine', desc: 'Prueba la conexión Qdrant y lógica de recuperación.', icon: Database },
                  { id: 'audio', label: 'Periféricos (Audio)', desc: 'Verifica si el sistema escucha tu micrófono.', icon: Mic }
                ].map(mod => (
                  <div key={mod.id} className="glass-card flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 rounded-lg bg-white/5 text-blue-400">
                          <mod.icon size={20} />
                        </div>
                        <h4 className="font-bold">{mod.label}</h4>
                      </div>
                      <p className="text-sm text-gray-500 mb-6">{mod.desc}</p>

                      {testResults[mod.id] && (
                        <div className={`p-3 rounded-lg text-xs font-mono mb-4 border ${testResults[mod.id].status === 'success'
                          ? 'bg-green-500/10 border-green-500/20 text-green-400'
                          : 'bg-red-500/10 border-red-500/20 text-red-400'
                          }`}>
                          {testResults[mod.id].message}
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => runTest(mod.id)}
                      disabled={testing === mod.id}
                      className="w-full py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all text-sm font-semibold flex items-center justify-center gap-2"
                    >
                      {testing === mod.id ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
                      {testing === mod.id ? "Ejecutando..." : "Correr Diagnóstico"}
                    </button>
                  </div>
                ))}
              </div>

              {/* Danger Zone */}
              <div className="glass-card border-red-900/30 bg-red-900/5">
                <div className="flex flex-col md:flex-row justify-between items-center gap-6">
                  <div>
                    <h3 className="text-xl font-bold text-red-400 flex items-center gap-2 mb-1">
                      <AlertCircle size={22} /> Zona de Control Crítico
                    </h3>
                    <p className="text-gray-500 text-sm">Estas acciones afectan la disponibilidad de todos los servicios locales.</p>
                  </div>
                  <button
                    onClick={handleRestart}
                    className="px-8 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold shadow-lg shadow-red-600/20 transition-all flex items-center gap-2"
                  >
                    <RefreshCw size={18} /> Reiniciar Sistema
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'rag' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-2 glass-card">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-xl font-semibold flex items-center gap-2">
                      <Files size={20} className="text-blue-400" /> Archivos del Conocimiento
                    </h3>
                    <button onClick={fetchData} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                      <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                    </button>
                  </div>

                  <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                    {files.length === 0 ? (
                      <div className="text-center py-12 text-gray-500 italic">No hay archivos cargados.</div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-4 rounded-xl border border-white/5 bg-white/2 hover:bg-white/5 transition-all group">
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                              <Files size={20} />
                            </div>
                            <div>
                              <p className="font-medium">{file.name}</p>
                              <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                            </div>
                          </div>
                          <button
                            onClick={() => deleteFile(file.name)}
                            className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                          >
                            <Trash2 size={18} />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>

              <div className="glass-card flex flex-col items-center justify-center text-center group border-dashed hover:border-blue-500/50">
                <div className="p-6 rounded-full bg-blue-500/5 text-blue-400 group-hover:scale-110 transition-transform mb-4">
                  <Upload size={48} />
                </div>
                <h4 className="text-lg font-medium mb-1">Subir Información</h4>
                <div className="glass-card flex flex-col items-center justify-center text-center group border-dashed hover:border-blue-500/50">
                  <div className="p-6 rounded-full bg-blue-500/5 text-blue-400 group-hover:scale-110 transition-transform mb-4">
                    <Upload size={48} />
                  </div>
                  <h4 className="text-lg font-medium mb-1">Subir Información</h4>
                  <p className="text-sm text-gray-500 mb-6">PDF, TXT, MD para el cerebro</p>
                  <label className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-xl font-semibold cursor-pointer shadow-lg shadow-blue-500/20 transition-all">
                    Explorar
                    <input type="file" className="hidden" onChange={handleUpload} />
                  </label>
                </div>
              </div>

              {/* Danger Zone RAG */}
              <div className="glass-card border-red-900/30 bg-red-900/5">
                <div className="flex flex-col md:flex-row justify-between items-center gap-6">
                  <div>
                    <h3 className="text-lg font-bold text-red-400 flex items-center gap-2 mb-1">
                      <Trash2 size={20} /> Zona de Peligro
                    </h3>
                    <p className="text-gray-500 text-sm">Borrar todo el conocimiento adquirido.</p>
                  </div>
                  <button
                    onClick={handlePurge}
                    className="px-6 py-2 rounded-xl bg-red-600/80 hover:bg-red-500 text-white font-bold shadow-lg shadow-red-600/20 transition-all flex items-center gap-2 text-sm"
                  >
                    <Trash2 size={16} /> Purgar Memoria
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'config' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid grid-cols-1 md:grid-cols-2 gap-8"
            >
              {/* LLM Provider */}
              <div className="glass-card">
                <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                  <Cpu size={20} className="text-purple-400" /> Inteligencia (LLM)
                </h3>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Proveedor</label>
                    <select
                      value={config.LLM_PROVIDER}
                      onChange={(e) => updateConfig("LLM_PROVIDER", e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl p-3 outline-none focus:border-purple-500"
                    >
                      <option value="ollama">Ollama (Local - Gratis)</option>
                      <option value="openai">OpenAI (Cloud - Pago)</option>
                      <option value="gemini">Gemini (Cloud - Pago)</option>
                    </select>
                  </div>

                  {config.LLM_PROVIDER === 'ollama' && (
                    <div>
                      <label className="block text-sm text-gray-400 mb-2">Modelo Local</label>
                      <input
                        type="text"
                        value={config.OLLAMA_MODEL}
                        onBlur={(e) => updateConfig("OLLAMA_MODEL", e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl p-3 outline-none focus:border-purple-500"
                        placeholder="ej. qwen2.5:1.5b"
                      />
                    </div>
                  )}

                  {(config.LLM_PROVIDER === 'openai' || config.LLM_PROVIDER === 'gemini') && (
                    <div>
                      <label className="block text-sm text-gray-400 mb-2">API Key</label>
                      <input
                        type="password"
                        value={config.LLM_PROVIDER === 'openai' ? config.OPENAI_API_KEY : config.GEMINI_API_KEY}
                        onBlur={(e) => updateConfig(config.LLM_PROVIDER === 'openai' ? "OPENAI_API_KEY" : "GEMINI_API_KEY", e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl p-3 outline-none focus:border-purple-500"
                        placeholder="sk-..."
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Voice & STT */}
              <div className="glass-card">
                <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                  <Mic size={20} className="text-green-400" /> Voz (STT/TTS)
                </h3>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Idioma</label>
                    <div className="flex gap-4">
                      {['es', 'en'].map(lang => (
                        <button
                          key={lang}
                          onClick={() => updateConfig("LANGUAGE", lang)}
                          className={`flex-1 p-4 rounded-xl border transition-all uppercase font-bold ${config.STT_LANGUAGE === lang ? 'border-green-500 bg-green-500/10' : 'border-white/10 text-gray-500'}`}
                        >
                          {lang === 'es' ? 'Español' : 'English'}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-4">Clonación de Voz (.wav)</label>
                    <div className="space-y-3 mb-6">
                      {voices.length === 0 ? (
                        <p className="text-xs text-gray-600 italic">No hay muestras de voz subidas.</p>
                      ) : (
                        voices.map(v => (
                          <div key={v.name} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${config.TTS_VOICE_FILE === v.name ? 'border-blue-500 bg-blue-500/5' : 'border-white/5 bg-white/2'}`}>
                            <div className="flex items-center gap-3">
                              <input
                                type="radio"
                                name="activeVoice"
                                checked={config.TTS_VOICE_FILE === v.name}
                                onChange={() => updateConfig("TTS_VOICE_FILE", v.name)}
                                className="w-4 h-4 accent-blue-500"
                              />
                              <span className="text-sm font-medium truncate max-w-[150px]">{v.name}</span>
                            </div>
                            <button
                              onClick={() => deleteVoice(v.name)}
                              className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        ))
                      )}
                    </div>

                    <label className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-dashed border-white/20 hover:border-blue-500/50 hover:bg-blue-500/5 transition-all cursor-pointer text-sm text-gray-400 hover:text-blue-400">
                      <Upload size={16} /> Subir Muestra .wav
                      <input type="file" accept=".wav" className="hidden" onChange={handleVoiceUpload} />
                    </label>
                  </div>
                </div>
              </div>
            </motion.div>
          )}


          {activeTab === 'debug' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="glass-card"
            >
              <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                <Terminal size={20} className="text-pink-400" /> Consola de Depuración Interactiva
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Control Manual */}
                <div className="space-y-6">
                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <h4 className="font-bold text-gray-300 mb-2">Control de Voz</h4>
                    <p className="text-xs text-gray-500 mb-4">Si el Wake Word falla, fuerza al sistema a escuchar.</p>
                    <button
                      onClick={() => handleDebugAction('listen')}
                      className="w-full py-4 rounded-xl bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 font-bold flex items-center justify-center gap-2 transition-all"
                    >
                      <Mic size={20} /> FORZAR ESCUCHA
                    </button>
                  </div>

                  <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                    <h4 className="font-bold text-gray-300 mb-2">Entrada de Texto</h4>
                    <p className="text-xs text-gray-500 mb-4">Escribe un comando o texto para probar los módulos.</p>
                    <textarea
                      value={debugText}
                      onChange={(e) => setDebugText(e.target.value)}
                      className="w-full bg-black/40 border border-white/10 rounded-xl p-3 text-white outline-none focus:border-pink-500 min-h-[100px]"
                      placeholder="Escribe aquí (ej. 'Hola Jarvis' o un texto para TTS)..."
                    />
                  </div>
                </div>

                {/* Acciones de Texto */}
                <div className="space-y-4">
                  <button
                    onClick={() => handleDebugAction('chat')}
                    className="w-full p-4 rounded-xl bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 flex items-center justify-between group transition-all"
                  >
                    <div className="text-left">
                      <span className="block font-bold text-blue-400 group-hover:text-blue-300">Chat con Jarvis</span>
                      <span className="text-xs text-gray-500">Simula que hablaste este texto (Flujo completo)</span>
                    </div>
                    <MessageSquare size={20} className="text-blue-500 opacity-50 group-hover:opacity-100" />
                  </button>

                  <button
                    onClick={() => handleDebugAction('tts')}
                    className="w-full p-4 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 flex items-center justify-between group transition-all"
                  >
                    <div className="text-left">
                      <span className="block font-bold text-purple-400 group-hover:text-purple-300">Prueba TTS Directa</span>
                      <span className="text-xs text-gray-500">Solo sintetiza y habla el texto (Sin RAG)</span>
                    </div>
                    <Volume2 size={20} className="text-purple-500 opacity-50 group-hover:opacity-100" />
                  </button>

                  <button
                    onClick={() => handleDebugAction('rag')}
                    className="w-full p-4 rounded-xl bg-yellow-500/10 hover:bg-yellow-500/20 border border-yellow-500/30 flex items-center justify-between group transition-all"
                  >
                    <div className="text-left">
                      <span className="block font-bold text-yellow-400 group-hover:text-yellow-300">Consultar Cerebro (RAG)</span>
                      <span className="text-xs text-gray-500">Consulta la base de datos vectorial y muestra respuesta</span>
                    </div>
                    <Database size={20} className="text-yellow-500 opacity-50 group-hover:opacity-100" />
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main >

      {/* Notifications */}
      < div className="fixed bottom-8 right-8 space-y-2" >
        {msg && (
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 50 }}
            className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-xl glass border-white/10 ${msg.type === 'error' ? 'text-red-400' : 'text-green-400'
              }`}
          >
            {msg.type === 'error' ? <AlertCircle size={20} /> : <CheckCircle2 size={20} />}
            <span className="font-medium">{msg.text}</span>
          </motion.div>
        )
        }
      </div >
    </div >
  );
}

export default App;

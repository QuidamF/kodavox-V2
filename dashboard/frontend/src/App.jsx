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
  Menu,
  X,
  Volume1,
  Activity as StatusIcon
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import TTSTest from './TTSTest';

const API_BASE = "http://localhost:8080";
const ORCHESTRATOR_SOCKET = "http://localhost:5000"; // Puerto por defecto del SocketIO del orquestador

function App() {
  const [activeTab, setActiveTab] = useState('status');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [files, setFiles] = useState([]);
  const [voices, setVoices] = useState([]);
  const [config, setConfig] = useState({});
  const [health, setHealth] = useState({});
  const [healthInterval, setHealthInterval] = useState(30);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [testing, setTesting] = useState(null);
  const [ragConfig, setRagConfig] = useState({
    persona: "",
    system_instructions: "",
    rag_k: 4,
    rag_max_context: 6000,
    rag_temperature: 0.1,
    rag_max_length: 1024,
    ollama_timeout: 300
  });
  const [ttsConfig, setTtsConfig] = useState({
    voice_sample: "",
    language: "es"
  });
  const [sttConfig, setSttConfig] = useState({
    language: "es",
    beam_size: 5
  });

  // Estados en tiempo real del orquestador
  const [orchState, setOrchState] = useState('OFFLINE');
  const [logs, setLogs] = useState([]);
  const [lastTranscript, setLastTranscript] = useState("");
  const [lastResponse, setLastResponse] = useState("");
  const [audioEnergy, setAudioEnergy] = useState(0);
  const [vadActive, setVadActive] = useState(false);

  // Debug State
  const [debugText, setDebugText] = useState("");

  const socketRef = useRef();
  const audioContextRef = useRef(null);
  const nextStartTimeRef = useRef(0);
  const activeStreamIdRef = useRef(0);
  const activeSourcesRef = useRef([]);

  useEffect(() => {
    fetchData();
    // Health polling is now managed via healthInterval state and a dedicated effect

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
      const answer = data.text || data.answer;
      setLastResponse(answer);
      addLog(`AI: ${answer}`);
    });

    socketRef.current.on('vad_speech_start', () => {
      setVadActive(true);
      addLog(`VAD: Inicio de voz detectado`);
    });

    socketRef.current.on('vad_speech_end', () => {
      setVadActive(false);
      addLog(`VAD: Fin de frase (silencio)`);
    });

    socketRef.current.on('audio_stop', (data) => {
      console.log("[Audio] Stopping playback (Barge-in)");
      // Invalidate current stream: Sync to the explicitly cancelled stream_id if provided
      if (data && data.stream_id) {
        activeStreamIdRef.current = data.stream_id;
      } else {
        activeStreamIdRef.current += 0.5; // Fallback
      }

      // Stop all currently playing and scheduled sources
      if (activeSourcesRef.current) {
        activeSourcesRef.current.forEach(source => {
          try {
            source.stop();
            source.disconnect();
          } catch (e) { }
        });
        activeSourcesRef.current = [];
      }

      // Reset scheduling time, keep context alive
      if (audioContextRef.current) {
        nextStartTimeRef.current = audioContextRef.current.currentTime;
      } else {
        nextStartTimeRef.current = 0;
      }
    });

    socketRef.current.on('audio_playback_chunk', async (data) => {
      try {
        const streamId = data.stream_id || 0;

        // Strict De-duplication + Backend Restart Detection
        const streamDiff = activeStreamIdRef.current - streamId;

        // If the streamId is older but the gap is enormous (> 100000), it means the backend restarted
        // and its internal stream_id counter reset to 0, while the frontend still held a large number (like a Unix timestamp).
        if (streamId < activeStreamIdRef.current && Math.abs(streamDiff) < 100000) {
          console.warn(`[Audio] Dropping zombie chunk: ${streamId} is older than active ${activeStreamIdRef.current}`);
          return;
        } else if (streamId < activeStreamIdRef.current && Math.abs(streamDiff) >= 100000) {
          console.log(`[Audio] Backend restart detected (Huge ID drop). Resetting stream counter to ${streamId}`);
          activeStreamIdRef.current = streamId - 1; // Force acceptance
        }

        // Detect new stream and force reset if needed (Self-Correcting Stream Switch)
        if (streamId > activeStreamIdRef.current) {
          console.log(`[Audio] New stream detected: ${streamId}. Resetting buffers.`);
          activeStreamIdRef.current = streamId;

          // Stop old sources without destroying the context
          activeSourcesRef.current.forEach(source => {
            try {
              source.stop();
              source.disconnect();
            } catch (e) { }
          });
          activeSourcesRef.current = [];

          if (audioContextRef.current) {
            nextStartTimeRef.current = audioContextRef.current.currentTime;
          } else {
            nextStartTimeRef.current = 0;
          }
        }

        if (!audioContextRef.current) {
          audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        }
        const ctx = audioContextRef.current;
        if (ctx.state === 'suspended' || ctx.state === 'closed') {
          if (ctx.state === 'suspended') await ctx.resume();
        }

        // Decode base64 
        const b64Data = data.data || data;
        const binaryString = window.atob(b64Data);
        const len = binaryString.length;

        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }

        const int16View = new Int16Array(bytes.buffer);
        const float32Buffer = ctx.createBuffer(1, int16View.length, 24000);
        const channelData = float32Buffer.getChannelData(0);

        for (let i = 0; i < int16View.length; i++) {
          channelData[i] = int16View[i] / 32768.0;
        }

        const source = ctx.createBufferSource();
        source.buffer = float32Buffer;
        source.connect(ctx.destination);

        const currentTime = ctx.currentTime;
        if (nextStartTimeRef.current < currentTime) {
          nextStartTimeRef.current = currentTime;
        }

        const startAt = nextStartTimeRef.current;
        source.start(startAt);

        // Track the source and clean it up when ended
        activeSourcesRef.current.push(source);
        source.onended = () => {
          activeSourcesRef.current = activeSourcesRef.current.filter(s => s !== source);
        };

        nextStartTimeRef.current = startAt + float32Buffer.duration;

      } catch (e) {
        console.error("Error playing audio chunk", e);
      }
    });

    return () => {
      if (socketRef.current) socketRef.current.disconnect();
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        try { audioContextRef.current.close(); } catch (e) { }
      }
    };
  }, []);

  // Dedicated effect for health polling
  useEffect(() => {
    const timer = setInterval(fetchHealth, healthInterval * 1000);
    return () => clearInterval(timer);
  }, [healthInterval]);

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
      if (configRes.data.HEALTH_CHECK_INTERVAL) {
        setHealthInterval(parseInt(configRes.data.HEALTH_CHECK_INTERVAL));
      }
      fetchRagConfig();
      fetchTtsConfig();
      fetchSttConfig();
      fetchHealth();
    } catch (err) {
      showMsg("Backend de gestión no disponible", "error");
    }
    setLoading(false);
  };

  const fetchRagConfig = async () => {
    try {
      const res = await axios.get(`${API_BASE}/rag/config`);
      setRagConfig(res.data);
    } catch (err) {
      console.error("Error fetching RAG config:", err);
    }
  };

  const saveRagConfig = async (newConfig) => {
    try {
      await axios.post(`${API_BASE}/rag/config`, newConfig);
      setRagConfig(newConfig);
      showMsg("Configuración RAG guardada");
    } catch (err) {
      showMsg("Error al guardar configuración RAG", "error");
    }
  };

  const fetchTtsConfig = async () => {
    try {
      const res = await axios.get(`${API_BASE}/tts/config`);
      setTtsConfig(res.data);
    } catch (err) {
      console.error("Error fetching TTS config:", err);
    }
  };

  const saveTtsConfig = async (newConfig) => {
    try {
      await axios.post(`${API_BASE}/tts/config`, newConfig);
      setTtsConfig(newConfig);
      showMsg("Configuración de Voz guardada");
    } catch (err) {
      showMsg("Error al guardar configuración de Voz", "error");
    }
  };

  const fetchSttConfig = async () => {
    try {
      const res = await axios.get(`${API_BASE}/stt/config`);
      setSttConfig(res.data);
    } catch (err) {
      console.error("Error fetching STT config:", err);
    }
  };

  const saveSttConfig = async (newConfig) => {
    try {
      await axios.post(`${API_BASE}/stt/config`, newConfig);
      setSttConfig(newConfig);
      showMsg("Configuración STT guardada");
    } catch (err) {
      showMsg("Error al guardar configuración STT", "error");
    }
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

    if (module === 'vad') {
      // Test de VAD
      // Forzamos al orquestador a escuchar
      if (socketRef.current) {
          socketRef.current.emit('manual_listen', {});
      }

      let started = false;
      let ended = false;
      const onStart = () => { started = true; };
      const onEnd = () => { ended = true; };
      
      socketRef.current.on('vad_speech_start', onStart);
      socketRef.current.on('vad_speech_end', onEnd);
      
      showMsg("HABLE al micrófono ahora, luego haga SILENCIO...", "info");
      
      const checkVad = new Promise((resolve) => {
        const start = Date.now();
        const checker = setInterval(() => {
          if (started && ended) {
            clearInterval(checker);
            resolve({ status: 'success', message: 'VAD detectó inicio y fin del habla correctamente.' });
          }
          // Timeout de 10 segundos
          if (Date.now() - start > 10000) {
            clearInterval(checker);
            if (started && !ended) resolve({ status: 'error', message: 'VAD detectó inicio pero no fin (falta silencio).' });
            else resolve({ status: 'error', message: 'No se detectó habla en absoluto.' });
          }
        }, 100);
      });
      
      const res = await checkVad;
      socketRef.current.off('vad_speech_start', onStart);
      socketRef.current.off('vad_speech_end', onEnd);
      
      setTestResults(prev => ({ ...prev, [module]: res }));
      if (res.status === 'success') showMsg("Prueba de VAD exitosa");
      else showMsg("Fallo en prueba de VAD", "error");
      
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

  const handleDebugAction = async (action) => {
    if (!socketRef.current) return;

    // Ensure AudioContext is running on user gesture
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    }
    if (audioContextRef.current.state === 'suspended') {
      try {
        await audioContextRef.current.resume();
      } catch (e) {
        console.error("Audio resume failed", e);
      }
    }

    switch (action) {
      case 'listen':
        socketRef.current.emit('manual_listen', {});
        showMsg("Escucha manual activada");
        break;
      case 'chat':
        if (!debugText) return;
        setLastTranscript(debugText);
        setLastResponse("");
        socketRef.current.emit('process_text', { text: debugText });
        showMsg(`Enviado al chat: ${debugText}`);
        break;
      case 'tts':
        if (!debugText) return;
        setLastTranscript("");
        setLastResponse("");
        socketRef.current.emit('speak_text', { text: debugText });
        showMsg("Enviado a TTS");
        break;
      case 'rag':
        if (!debugText) return;
        setLastTranscript(debugText);
        setLastResponse("");
        socketRef.current.emit('query_rag', { text: debugText });
        showMsg("Consultando RAG...");
        break;
    }
  };

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-6xl mx-auto">
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-center mb-8 md:mb-12 gap-6 md:gap-0">
        <div className="text-center md:text-left">
          <h1 className="text-4xl md:text-6xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-orange-400 via-pink-500 to-purple-600 animate-gradient-x pb-2">
            SAMANTA
          </h1>
          <p className="text-gray-600 mt-2 text-lg font-light tracking-wide">Tu Asistente Inteligente</p>
        </div>
        <div className="flex flex-wrap justify-center items-center gap-4">
          <button
            onClick={fetchHealth}
            className="p-2 hover:bg-white/80 rounded-full transition-colors order-last md:order-none"
            title="Validar conexión ahora"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
          {Object.entries(health).map(([svc, status]) => (
            <div key={svc} className="flex items-center gap-2 px-3 py-1 rounded-full border border-gray-300 bg-white/60 text-sm">
              <div className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-green-500 shadow-[0_0_8px_#22c55e]' :
                status === 'offline' ? 'bg-red-500' : 'bg-yellow-500'
                }`} />
              <span className="capitalize text-gray-900">{svc}</span>
            </div>
          ))}
        </div>
      </header>

      {/* Tabs */}
      {/* Navigation - Responsive Wrapper */}
      <div className="relative mb-8 z-50">
        {/* Mobile Menu Button */}
        <div className="md:hidden flex justify-end mb-4">
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="p-2 rounded-lg bg-white/60 text-gray-800 shadow-sm border border-gray-300"
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        <AnimatePresence>
          {isMenuOpen && (
            <motion.nav
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="md:hidden flex flex-col gap-2 p-2 glass rounded-xl overflow-hidden mb-4"
            >
              {[
                { id: 'status', icon: StatusIcon, label: 'Estado' },
                { id: 'rag', icon: Database, label: 'Base de Datos (RAG)' },
                { id: 'config', icon: Settings, label: 'Configuración' },
                { id: 'tests', icon: Cpu, label: 'Pruebas' },
                { id: 'debug', icon: Terminal, label: 'Consola / Debug' },
                { id: 'ttstest', icon: Volume1, label: 'Test TTS' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => { setActiveTab(tab.id); setIsMenuOpen(false); }}
                  className={`flex items-center gap-2 px-6 py-3 rounded-lg transition-all w-full text-left ${activeTab === tab.id ? 'bg-orange-500 text-white' : 'hover:bg-white/60 text-gray-600'
                    }`}
                >
                  <tab.icon size={18} className={activeTab === tab.id ? "text-white" : "text-gray-500"} />
                  {tab.label}
                </button>
              ))}
            </motion.nav>
          )}
        </AnimatePresence>

        {/* Desktop Navigation (Hidden on Mobile) */}
        <nav className="hidden md:flex gap-2 p-1 glass rounded-xl w-fit">
          {[
            { id: 'status', icon: StatusIcon, label: 'Estado' },
            { id: 'rag', icon: Database, label: 'Base de Datos (RAG)' },
            { id: 'config', icon: Settings, label: 'Configuración' },
            { id: 'tests', icon: Cpu, label: 'Pruebas' },
            { id: 'debug', icon: Terminal, label: 'Consola / Debug' },
            { id: 'ttstest', icon: Volume1, label: 'Test TTS Aislado' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-6 py-2 rounded-lg transition-all ${activeTab === tab.id ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/20' : 'hover:bg-white/60 text-gray-600'
                }`}
            >
              <tab.icon size={18} className={activeTab === tab.id ? "text-white" : "text-gray-500"} />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

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
                  <Zap size={20} className="text-amber-400" /> Motor de Voz
                </h3>
                <div className="flex flex-col items-center justify-center py-8">
                  <div className={`text-3xl mb-4 font-black tracking-tighter break-words text-center px-2 ${orchState === 'OFFLINE' ? 'text-gray-700' : 'text-orange-500'
                    }`}>
                    {(() => {
                      const stateMap = {
                        'IDLE': 'Inactivo',
                        'LISTENING_WAKEWORD': 'Esperando',
                        'LISTENING_USER': 'Escuchando',
                        'PROCESSING': 'Procesando',
                        'SPEAKING': 'Hablando',
                        'OFFLINE': 'Desconectado'
                      };
                      return stateMap[orchState] || orchState;
                    })()}
                  </div>
                  <p className="text-gray-500 text-sm">Estado actual del flujo de IA</p>

                  {/* Visualizador de Micrófono */}
                  <div className="mt-6 w-full px-8 flex flex-col items-center">
                    <div className="flex items-center gap-2 mb-2">
                      <Mic size={16} className={vadActive ? "text-red-500 animate-pulse" : (audioEnergy > 5 ? "text-green-400" : "text-gray-600")} />
                      <span className="text-xs text-gray-500 uppercase font-bold">
                        {vadActive ? "DETECTANDO VOZ (VAD)" : "Nivel Micrófono"}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-white/60 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-orange-500 to-pink-500"
                        animate={{ width: `${audioEnergy}%` }}
                        transition={{ type: "tween", ease: "linear", duration: 0.05 }}
                      />
                    </div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 uppercase tracking-wider font-bold text-[10px]">Wake Word</span>
                    <span className={health.wakeword === 'online' ? 'text-green-500' : 'text-red-500'}>{health.wakeword || 'pending'}</span>
                  </div>
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
                  <MessageSquare size={20} className="text-orange-400" /> Conversación Activa
                </h3>
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-white/60 border border-gray-200 min-h-[80px]">
                    <span className="text-[10px] text-orange-400 font-bold uppercase block mb-1">Último que escuché</span>
                    <p className="text-lg text-gray-800">{lastTranscript || "Esperando voz..."}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-pink-500/5 border border-pink-500/10 min-h-[80px]">
                    <span className="text-[10px] text-pink-400 font-bold uppercase flex items-center gap-2 mb-1">
                      Respuesta de Samanta
                      {orchState === 'PROCESSING' && (
                        <motion.div
                          animate={{ opacity: [0.4, 1, 0.4] }}
                          transition={{ duration: 1, repeat: Infinity }}
                          className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_#22c55e]"
                        />
                      )}
                    </span>
                    <p className="text-lg text-pink-100">{lastResponse || "Sin respuesta todavía"}</p>
                  </div>
                </div>

                <h3 className="text-lg font-semibold mt-8 mb-4 flex items-center gap-2">
                  <Terminal size={20} className="text-gray-600" /> Eventos del Sistema
                </h3>
                <div className="bg-black/40 rounded-xl p-4 font-mono text-xs overflow-y-auto h-[160px] border border-gray-200">
                  {logs.map((log, i) => (
                    <div key={i} className="mb-1">
                      <span className="text-gray-600 mr-2">[{log.time}]</span>
                      <span className="text-gray-900">{log.msg}</span>
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
                  { id: 'audio', label: 'Periféricos (Audio)', desc: 'Verifica si el sistema escucha tu micrófono.', icon: Mic },
                  { id: 'vad', label: 'Voice Activity (VAD)', desc: 'Prueba si detecta inicio y fin del habla.', icon: Activity }
                ].map(mod => (
                  <div key={mod.id} className="glass-card flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 rounded-lg bg-white/60 text-orange-400">
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
                      className="w-full py-2 rounded-xl bg-white/60 hover:bg-white/80 border border-gray-300 transition-all text-sm font-semibold flex items-center justify-center gap-2"
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
                      <Files size={20} className="text-orange-400" /> Archivos del Conocimiento
                    </h3>
                    <button onClick={fetchData} className="p-2 hover:bg-white/80 rounded-full transition-colors">
                      <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                    </button>
                  </div>

                  <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                    {files.length === 0 ? (
                      <div className="text-center py-12 text-gray-500 italic">No hay archivos cargados.</div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-4 rounded-xl border border-gray-200 bg-white/80 hover:bg-white/60 transition-all group">
                          <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-orange-500/10 text-orange-400">
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

              <div className="glass-card flex flex-col items-center justify-center text-center group border-dashed hover:border-orange-500/50">
                <div className="p-6 rounded-full bg-orange-500/5 text-orange-400 group-hover:scale-110 transition-transform mb-4">
                  <Upload size={48} />
                </div>
                <h4 className="text-lg font-medium mb-1">Subir Información</h4>
                <p className="text-sm text-gray-500 mb-6">PDF, TXT, MD para el cerebro</p>
                <label className="bg-orange-600 hover:bg-orange-500 px-8 py-3 rounded-xl font-semibold cursor-pointer shadow-lg shadow-orange-500/20 transition-all">
                  Explorar
                  <input type="file" className="hidden" onChange={handleUpload} />
                </label>
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
              className="space-y-8"
            >
              {/* Comportamiento y Personalidad */}
              <div className="glass-card">
                <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                  <MessageSquare size={20} className="text-pink-400" /> Personalidad del Agente
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-600 mb-2">Instrucciones de Sistema (Roleplay)</label>
                    <textarea
                      value={ragConfig.persona}
                      onChange={(e) => setRagConfig({ ...ragConfig, persona: e.target.value })}
                      className="w-full bg-white/60 border border-gray-300 rounded-xl p-4 outline-none focus:border-blue-500 min-h-[120px] text-gray-800"
                      placeholder="Ej: Eres un asistente sarcástico y divertido..."
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-2">Instrucciones del Sistema (Cómo usar el RAG)</label>
                    <textarea
                      value={ragConfig.system_instructions}
                      onChange={(e) => setRagConfig({ ...ragConfig, system_instructions: e.target.value })}
                      className="w-full bg-white/60 border border-gray-300 rounded-xl p-4 outline-none focus:border-purple-500 min-h-[140px] text-gray-800 font-mono text-sm"
                      placeholder="Ej: INSTRUCCIONES CRÍTICAS:\n1. SOLO puedes responder usando la información del CONTEXTO...\n2. Si la pregunta NO puede responderse..."
                    />
                    <p className="text-[10px] text-blue-500 mt-2 italic flex items-center gap-1">
                      <AlertCircle size={10} /> Tip: Según políticas de Meta, para WhatsApp/Messenger descríbete como un "Asistente de agendamiento de citas".
                    </p>
                  </div>
                  <div className="flex justify-end">
                    <button
                      onClick={() => saveRagConfig(ragConfig)}
                      className="px-6 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-bold transition-all flex items-center gap-2"
                    >
                      <Save size={18} /> Guardar Personalidad
                    </button>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Parámetros Técnicos RAG */}
                <div className="glass-card">
                  <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                    <Database size={20} className="text-orange-400" /> Parámetros de RAG
                  </h3>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">K (Docs a recuperar)</label>
                        <input
                          type="number"
                          value={ragConfig.rag_k}
                          onChange={(e) => setRagConfig({ ...ragConfig, rag_k: parseInt(e.target.value) })}
                          className="w-full bg-white/60 border border-gray-300 rounded-xl p-2 outline-none focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Temperatura</label>
                        <input
                          type="number"
                          step="0.1"
                          value={ragConfig.rag_temperature}
                          onChange={(e) => setRagConfig({ ...ragConfig, rag_temperature: parseFloat(e.target.value) })}
                          className="w-full bg-white/60 border border-gray-300 rounded-xl p-2 outline-none focus:border-blue-500"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Máximo Contexto (Caracteres)</label>
                      <input
                        type="number"
                        value={ragConfig.rag_max_context}
                        onChange={(e) => setRagConfig({ ...ragConfig, rag_max_context: parseInt(e.target.value) })}
                        className="w-full bg-white/60 border border-gray-300 rounded-xl p-2 outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="flex justify-end pt-2">
                      <button
                        onClick={() => saveRagConfig(ragConfig)}
                        className="px-6 py-2 rounded-xl bg-orange-600/20 hover:bg-orange-600/30 text-orange-400 border border-orange-500/30 font-bold transition-all flex items-center gap-2"
                      >
                        <Save size={18} /> Aplicar Parámetros
                      </button>
                    </div>
                  </div>
                </div>

                {/* Optimización de Red / Monitoreo */}
                <div className="glass-card">
                  <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                    <Activity size={20} className="text-blue-400" /> Monitoreo de Red
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-gray-600 mb-2">Frecuencia de salud (segundos)</label>
                      <input
                        type="number"
                        min="5"
                        max="600"
                        value={healthInterval}
                        onChange={(e) => setHealthInterval(parseInt(e.target.value))}
                        className="w-full bg-white/60 border border-gray-300 rounded-xl p-3 outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => updateConfig("HEALTH_CHECK_INTERVAL", healthInterval.toString())}
                        className="flex-1 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold transition-all flex items-center justify-center gap-2"
                      >
                        <Save size={18} /> Aplicar
                      </button>
                      <button
                        onClick={fetchHealth}
                        className="px-4 py-3 rounded-xl bg-white/60 hover:bg-white/80 border border-gray-300 transition-all font-semibold flex items-center gap-2"
                      >
                        <RefreshCw size={18} /> Validar
                      </button>
                    </div>
                  </div>
                </div>

                {/* Inteligencia (LLM) */}
                <div className="glass-card">
                  <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                    <Cpu size={20} className="text-violet-400" /> Inteligencia (LLM)
                  </h3>
                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm text-gray-600 mb-2">Proveedor</label>
                      <select
                        value={config.LLM_PROVIDER}
                        onChange={(e) => updateConfig("LLM_PROVIDER", e.target.value)}
                        className="w-full bg-white/60 border border-gray-300 rounded-xl p-3 outline-none focus:border-purple-500"
                      >
                        <option value="ollama">Ollama (Local)</option>
                        <option value="openai">OpenAI (Cloud)</option>
                        <option value="gemini">Gemini (Cloud)</option>
                      </select>
                    </div>
                    {config.LLM_PROVIDER === 'ollama' && (
                      <input
                        type="text"
                        value={config.OLLAMA_MODEL}
                        onBlur={(e) => updateConfig("OLLAMA_MODEL", e.target.value)}
                        className="w-full bg-white/60 border border-gray-300 rounded-xl p-3 outline-none focus:border-purple-500"
                        placeholder="ej. qwen2.5:1.5b"
                      />
                    )}
                  </div>
                </div>

                {/* Voz & STT */}
                <div className="glass-card">
                  <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
                    <Mic size={20} className="text-emerald-400" /> Voz y Transcripción
                  </h3>
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Idioma</label>
                        <select
                          value={ttsConfig.language}
                          onChange={(e) => saveTtsConfig({ ...ttsConfig, language: e.target.value })}
                          className="w-full bg-white/60 border border-gray-300 rounded-xl p-2 outline-none focus:border-pink-500"
                        >
                          <option value="es">Español</option>
                          <option value="en">English</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Beam Size (STT)</label>
                        <input
                          type="number"
                          value={sttConfig.beam_size}
                          onChange={(e) => saveSttConfig({ ...sttConfig, beam_size: parseInt(e.target.value) })}
                          className="w-full bg-white/60 border border-gray-300 rounded-xl p-2 outline-none focus:border-orange-500"
                        />
                      </div>
                    </div>

                    <div className="space-y-4">
                      <label className="block text-sm text-gray-600 font-bold">Muestras de Voz (.wav)</label>
                      <div className="space-y-2 max-h-[200px] overflow-y-auto pr-2 custom-scrollbar">
                        {voices.length === 0 ? (
                          <p className="text-xs text-gray-500 italic pb-4">No hay muestras subidas.</p>
                        ) : (
                          voices.map(v => (
                            <div key={v.name} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${ttsConfig.voice_sample === v.name ? 'border-orange-500 bg-orange-500/5' : 'border-gray-200 bg-white/40'}`}>
                              <div className="flex items-center gap-2">
                                <input
                                  type="radio"
                                  checked={ttsConfig.voice_sample === v.name}
                                  onChange={() => saveTtsConfig({ ...ttsConfig, voice_sample: v.name })}
                                  className="w-4 h-4 accent-orange-500"
                                />
                                <span className="text-sm font-medium truncate max-w-[150px]">{v.name}</span>
                              </div>
                              <button
                                onClick={() => deleteVoice(v.name)}
                                className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all"
                                title="Eliminar voz"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          ))
                        )}
                      </div>

                      <label className="w-full flex items-center justify-center gap-3 py-4 rounded-xl border-2 border-dashed border-gray-300 hover:border-orange-500/50 hover:bg-orange-500/5 transition-all cursor-pointer text-sm font-semibold text-gray-600">
                        <Upload size={18} className="text-orange-500" />
                        <span>Subir Fragmento .wav</span>
                        <input type="file" accept=".wav" className="hidden" onChange={handleVoiceUpload} />
                      </label>
                      <p className="text-[10px] text-gray-400 text-center italic">Sube fragmentos de audio para clonar voces personalizadas.</p>
                    </div>
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
                <Terminal size={20} className="text-pink-400" /> Consola Interactiva
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="space-y-6">
                  <button onClick={() => handleDebugAction('listen')} className="w-full py-4 rounded-xl bg-red-500/20 text-red-400 border border-red-500/30 font-bold flex items-center justify-center gap-2 transition-all">
                    <Mic size={20} /> FORZAR ESCUCHA
                  </button>
                  <textarea value={debugText} onChange={(e) => setDebugText(e.target.value)} className="w-full bg-black/40 border border-gray-300 rounded-xl p-3 text-white outline-none focus:border-pink-500 min-h-[100px]" placeholder="Texto de prueba..." />
                </div>
                <div className="space-y-4">
                  <button onClick={() => handleDebugAction('chat')} className="w-full p-4 rounded-xl bg-blue-500/10 border border-blue-500/30 flex justify-between items-center group transition-all">
                    <span className="font-bold text-blue-400">Chat con Samanta</span>
                    <MessageSquare size={20} />
                  </button>
                  <button onClick={() => handleDebugAction('tts')} className="w-full p-4 rounded-xl bg-purple-500/10 border border-purple-500/30 flex justify-between items-center group transition-all">
                    <span className="font-bold text-purple-400">Prueba TTS</span>
                    <Volume2 size={20} />
                  </button>
                  <button onClick={() => handleDebugAction('rag')} className="w-full p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex justify-between items-center group transition-all">
                    <span className="font-bold text-amber-400">Consulta RAG Directa</span>
                    <Database size={20} />
                  </button>
                </div>
              </div>

              {/* Nueva sección de visualización de respuestas textuales en Debug */}
              <div className="mt-8 pt-8 border-t border-gray-200">
                <h4 className="text-sm font-bold text-gray-400 uppercase tracking-widest mb-4">Salida de Texto</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-black/5 border border-gray-200">
                    <span className="text-[10px] text-blue-400 font-bold uppercase block mb-1">Entrada Detectada</span>
                    <p className="text-sm text-gray-700 italic">{lastTranscript || "Sin transcripción reciente..."}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-pink-500/5 border border-pink-500/10">
                    <span className="text-[10px] text-pink-400 font-bold uppercase flex items-center gap-2 mb-1">
                      Respuesta de Samanta
                      {orchState === 'PROCESSING' && (
                        <motion.div
                          animate={{ opacity: [0.4, 1, 0.4] }}
                          transition={{ duration: 1, repeat: Infinity }}
                          className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_#22c55e]"
                        />
                      )}
                    </span>
                    <p className="text-sm text-gray-800">{lastResponse || "Esperando respuesta..."}</p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'ttstest' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <TTSTest />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <div className="fixed bottom-8 right-8 space-y-2">
        {msg && (
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 50 }}
            className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-xl glass border-gray-300 ${msg.type === 'error' ? 'text-red-400' : 'text-green-400'}`}
          >
            {msg.type === 'error' ? <AlertCircle size={20} /> : <CheckCircle2 size={20} />}
            <span className="font-medium">{msg.text}</span>
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default App;

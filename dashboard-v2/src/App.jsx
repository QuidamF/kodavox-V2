import { useState, useEffect, useRef } from 'react'
import { io } from 'socket.io-client'
import { 
  Mic, MicOff, MessageSquare, Cpu, Volume2, 
  Database, Upload, Trash, Plus, User, 
  Settings, Activity, Key, CheckSquare, CreditCard, UploadCloud, DownloadCloud, AlertTriangle, Loader2
} from 'lucide-react'

// Nos conectaremos al motor monolítico
const PORT = import.meta.env.VITE_ENGINE_PORT || '5000';
const HOSTNAME = window.location.hostname || 'localhost';
const PROTOCOL = window.location.protocol === 'https:' ? 'https' : 'http';

const SOCKET_URL = `${PROTOCOL}://${HOSTNAME}:${PORT}`;
const API_URL = `${PROTOCOL}://${HOSTNAME}:${PORT}/api`;

function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [connected, setConnected] = useState(false);
  
  // Telemetry States
  const [vadActive, setVadActive] = useState(false);
  const micEnergyTextRef = useRef(null);
  const micEnergyBarRef = useRef(null);
  const [sttText, setSttText] = useState("");
  const [llmStream, setLlmStream] = useState("");
  const [llmProvider, setLlmProvider] = useState("");
  const [ttsActive, setTtsActive] = useState(false);
  const [engineState, setEngineState] = useState("idle");
  const [sessionActive, setSessionActive] = useState(false);

  // RAG States
  const [collections, setCollections] = useState([]);
  const [activeCollection, setActiveCollection] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // Config States
  const [personalityPrompt, setPersonalityPrompt] = useState("");
  const [llmTemperature, setLlmTemperature] = useState(0.7);
  const [ragStrictMode, setRagStrictMode] = useState(false);
  const [elevenlabsVoices, setElevenlabsVoices] = useState([]);
  const [activeVoiceId, setActiveVoiceId] = useState("");
  const [newVoiceName, setNewVoiceName] = useState("");
  const [newVoiceId, setNewVoiceId] = useState("");
  const [voiceAddMode, setVoiceAddMode] = useState("id"); // "id" or "clone"
  const [cloneVoiceName, setCloneVoiceName] = useState("");
  const [cloneFile, setCloneFile] = useState(null);
  const [isCloning, setIsCloning] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [wakeWord, setWakeWord] = useState("");
  const [wakeTimeout, setWakeTimeout] = useState(10);
  const [vadThreshold, setVadThreshold] = useState(0.6);
  const [vadEndSilence, setVadEndSilence] = useState(0.7);
  const [sttMinSpeech, setSttMinSpeech] = useState(0.3);
  const [vadPrePadding, setVadPrePadding] = useState(0.2);
  const [piperLengthScale, setPiperLengthScale] = useState(0.85);
  const [piperNoiseScale, setPiperNoiseScale] = useState(0.75);
  const [ttsProvider, setTtsProvider] = useState("elevenlabs");
  const [sttProvider, setSttProvider] = useState("whisper");
  const [testVoiceText, setTestVoiceText] = useState("Hola, esta es una prueba de voz de KodaVox.");
  const [voiceStability, setVoiceStability] = useState(0.5);
  const [voiceSimilarity, setVoiceSimilarity] = useState(0.75);
  const [voiceStyle, setVoiceStyle] = useState(0.0);
  const [voiceSpeakerBoost, setVoiceSpeakerBoost] = useState(true);

  // Export/Import States
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [exportIncludeEnv, setExportIncludeEnv] = useState(false);
  const [exportIncludeRag, setExportIncludeRag] = useState(false);
  const [exportIncludeCredentials, setExportIncludeCredentials] = useState(true);

  // Diagnostics States
  const [healthStatus, setHealthStatus] = useState(null);
  const [providersStatus, setProvidersStatus] = useState(null);
  const [usageStats, setUsageStats] = useState({});
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [nativeAudioOutput, setNativeAudioOutput] = useState(true);
  const [robotFaceSync, setRobotFaceSync] = useState(false);

  // Credentials Setup Wizard
  const [credentialsStatus, setCredentialsStatus] = useState(null);
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [inputKeys, setInputKeys] = useState({
    OPENAI_API_KEY: '',
    GEMINI_API_KEY: '',
    ELEVENLABS_API_KEY: ''
  });
  const [isSavingKeys, setIsSavingKeys] = useState(false);

  // Pricing (per 1M)
  const [costRates, setCostRates] = useState(() => {
    const saved = localStorage.getItem("kodavox_costs");
    if (saved) return JSON.parse(saved);
    return { openai: 0.15, gemini: 0.0, elevenlabs: 15.0 }; // Default placeholders
  });

  const saveCostRates = async (newRates) => {
    setCostRates(newRates);
    localStorage.setItem("kodavox_costs", JSON.stringify(newRates));
    try {
      await fetch(`${API_URL}/config/hardware`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cost_rates: newRates })
      });
    } catch (e) {
      console.error("Error saving cost rates to backend", e);
    }
  };

  const fetchConfig = async () => {
    try {
      const resP = await fetch(`${API_URL}/config/personality`);
      if (resP.ok) {
        const data = await resP.json();
        setPersonalityPrompt(data.personality_prompt);
        if (data.llm_temperature !== undefined) setLlmTemperature(data.llm_temperature);
        if (data.rag_strict_mode !== undefined) setRagStrictMode(data.rag_strict_mode);
      }
      const resV = await fetch(`${API_URL}/config/voices`);
      if (resV.ok) {
        const data = await resV.json();
        setElevenlabsVoices(data.voices);
        setActiveVoiceId(data.active_voice_id);
        if (data.settings) {
          setVoiceStability(data.settings.stability);
          setVoiceSimilarity(data.settings.similarity_boost);
          setVoiceStyle(data.settings.style);
          setVoiceSpeakerBoost(data.settings.use_speaker_boost);
        }
      }
      const resW = await fetch(`${API_URL}/config/wakeword`);
      if (resW.ok) {
        const data = await resW.json();
        setWakeWord(data.wake_word);
        setWakeTimeout(data.wake_session_timeout);
        if (data.vad_threshold !== undefined) setVadThreshold(data.vad_threshold);
        if (data.vad_end_silence_seconds !== undefined) setVadEndSilence(data.vad_end_silence_seconds);
        if (data.stt_min_speech_seconds !== undefined) setSttMinSpeech(data.stt_min_speech_seconds);
        if (data.vad_pre_padding_seconds !== undefined) setVadPrePadding(data.vad_pre_padding_seconds);
        if (data.piper_length_scale !== undefined) setPiperLengthScale(data.piper_length_scale);
        if (data.piper_noise_scale !== undefined) setPiperNoiseScale(data.piper_noise_scale);
        if (data.tts_provider) setTtsProvider(data.tts_provider);
        if (data.stt_provider) setSttProvider(data.stt_provider);
      }
      const resH = await fetch(`${API_URL}/config/hardware`);
      if (resH.ok) {
        const data = await resH.json();
        setNativeAudioOutput(data.native_audio_output);
        setRobotFaceSync(data.robot_face_sync);
        if (data.cost_rates) {
          setCostRates(data.cost_rates);
          localStorage.setItem("kodavox_costs", JSON.stringify(data.cost_rates));
        }
      }
    } catch (e) {
      console.error("Error fetching config:", e);
    }
  };

  const fetchCollections = async () => {
    try {
      const res = await fetch(`${API_URL}/rag/collections`);
      if (res.ok) {
        const data = await res.json();
        setCollections(data.collections);
        setActiveCollection(data.active);
      }
    } catch (e) {
      console.error("Error fetching collections:", e);
    }
  };

  const fetchDiagnostics = async () => {
    setIsCheckingHealth(true);
    try {
      const resHealth = await fetch(`${API_URL}/diagnostics/health`);
      if (resHealth.ok) setHealthStatus(await resHealth.json());

      const resProv = await fetch(`${API_URL}/diagnostics/providers`);
      if (resProv.ok) setProvidersStatus(await resProv.json());

      const resUsage = await fetch(`${API_URL}/diagnostics/usage`);
      if (resUsage.ok) setUsageStats(await resUsage.json());
    } catch (e) {
      console.error("Error fetching diagnostics:", e);
    } finally {
      setIsCheckingHealth(false);
    }
  };

  const fetchCredentialsStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/config/credentials/status`);
      if (res.ok) {
        const data = await res.json();
        setCredentialsStatus(data);
        
        // Determinar si falta alguna llave requerida
        const needsOpenAI = data.llm_provider === 'openai' && !data.OPENAI_API_KEY;
        const needsGemini = data.llm_provider === 'gemini' && !data.GEMINI_API_KEY;
        const needsElevenLabs = (data.stt_provider === 'elevenlabs' || data.tts_provider === 'elevenlabs') && !data.ELEVENLABS_API_KEY;
        
        if (needsOpenAI || needsGemini || needsElevenLabs) {
          setShowCredentialsModal(true);
        }
      }
    } catch (e) {
      console.error("Error fetching credentials status:", e);
    }
  };

  const handleSaveCredentials = async (e) => {
    e.preventDefault();
    setIsSavingKeys(true);
    try {
      const res = await fetch(`${API_URL}/config/credentials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(inputKeys)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.needs_restart) {
          setIsRestarting(true);
          setShowCredentialsModal(false);
          // Hacer polling hasta que vuelva a estar vivo
          const pollInterval = setInterval(async () => {
            try {
              const ping = await fetch(`${API_URL}/diagnostics/health`, { signal: AbortSignal.timeout(2000) });
              if (ping.ok) {
                clearInterval(pollInterval);
                window.location.reload();
              }
            } catch (e) {
              // Aún no despierta, ignorar
            }
          }, 3000);
        }
      }
    } catch (e) {
      console.error("Error saving credentials:", e);
      alert("Error al guardar credenciales");
      setIsSavingKeys(false);
    }
  };

  const handleCreateCollection = async (e) => {
    e.preventDefault();
    if (!newCollectionName.trim()) return;
    try {
      await fetch(`${API_URL}/rag/collections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newCollectionName.trim() })
      });
      setNewCollectionName("");
      fetchCollections();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteCollection = async (name) => {
    if (!confirm(`¿Eliminar colección '${name}'?`)) return;
    try {
      await fetch(`${API_URL}/rag/collections/${name}`, { method: "DELETE" });
      fetchCollections();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSetActive = async (e) => {
    const name = e.target.value;
    try {
      await fetch(`${API_URL}/rag/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name })
      });
      fetchCollections();
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const targetCollection = activeCollection || (collections.length > 0 ? collections[0] : null);
    if (!uploadFile || !targetCollection) return;
    
    setIsUploading(true);
    const formData = new FormData();
    formData.append("collection", targetCollection);
    formData.append("file", uploadFile);

    try {
      const res = await fetch(`${API_URL}/rag/upload`, {
        method: "POST",
        body: formData
      });
      if (res.ok) {
        alert("Archivo subido con éxito");
        setUploadFile(null);
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
      }
    } catch (e) {
      console.error(e);
      alert("Error al subir archivo");
    } finally {
      setIsUploading(false);
    }
  };

  const handleSaveWakeWord = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API_URL}/config/wakeword`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          word: wakeWord,
          timeout: wakeTimeout,
          vad_threshold: vadThreshold,
          vad_end_silence_seconds: vadEndSilence,
          stt_min_speech_seconds: sttMinSpeech,
          vad_pre_padding_seconds: vadPrePadding,
          piper_length_scale: piperLengthScale,
          piper_noise_scale: piperNoiseScale
        })
      });
      alert("Configuración de Wakeword y Calibración VAD guardada exitosamente");
    } catch (e) {
      console.error(e);
    }
  };

  const handleSavePersonality = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API_URL}/config/personality`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          personality_prompt: personalityPrompt,
          llm_temperature: llmTemperature,
          rag_strict_mode: ragStrictMode
        })
      });
      alert("Personalidad y parámetros de IA guardados exitosamente");
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddVoice = async (e) => {
    e.preventDefault();
    if (!newVoiceName.trim() || !newVoiceId.trim()) return;
    try {
      const res = await fetch(`${API_URL}/config/voices`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newVoiceName.trim(), id: newVoiceId.trim() })
      });
      if (res.ok) {
        setNewVoiceName("");
        setNewVoiceId("");
        fetchConfig();
      } else {
        const err = await res.json();
        alert(err.detail);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteVoice = async (id) => {
    if (!confirm(`¿Eliminar esta voz?`)) return;
    try {
      await fetch(`${API_URL}/config/voices/${id}`, { method: "DELETE" });
      fetchConfig();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSetActiveVoice = async (e) => {
    const id = e.target.value;
    try {
      await fetch(`${API_URL}/config/voices/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id })
      });
      fetchConfig();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveVoiceSettings = async () => {
    try {
      await fetch(`${API_URL}/config/voices/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stability: voiceStability,
          similarity_boost: voiceSimilarity,
          style: voiceStyle,
          use_speaker_boost: voiceSpeakerBoost
        })
      });
      alert("Configuración de voz guardada correctamente.");
    } catch (e) {
      console.error("Error saving voice settings:", e);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/mp3" });
        const file = new File([blob], "grabacion.mp3", { type: "audio/mp3" });
        setCloneFile(file);
      };
      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
    } catch (e) {
      alert("No se pudo acceder al micrófono.");
      console.error(e);
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
  };

  const handleCloneVoice = async (e) => {
    e.preventDefault();
    if (!cloneVoiceName.trim() || !cloneFile) {
      alert("Proporciona un nombre y un archivo de audio.");
      return;
    }
    setIsCloning(true);
    const formData = new FormData();
    formData.append("name", cloneVoiceName);
    formData.append("file", cloneFile);

    try {
      const res = await fetch(`${API_URL}/config/voices/clone`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        alert("Voz clonada exitosamente");
        setCloneVoiceName("");
        setCloneFile(null);
        fetchConfig();
        setVoiceAddMode("id");
      } else {
        const errorData = await res.json();
        alert(`Error al clonar: ${errorData.detail}`);
      }
    } catch (e) {
      console.error(e);
      alert("Error de conexión al clonar voz.");
    } finally {
      setIsCloning(false);
    }
  };

  const handleExportProfile = async () => {
    try {
      const res = await fetch(`${API_URL}/config/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          include_env: exportIncludeEnv,
          include_rag: exportIncludeRag,
          include_credentials: exportIncludeCredentials
        })
      });
      
      if (!res.ok) throw new Error('Error al exportar');
      
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'kodavox_full_profile.zip';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (e) {
      console.error(e);
      alert('Error al exportar perfil.');
    }
  };

  const handleImportProfile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!confirm("Esto sobrescribirá tu configuración actual. Si incluye archivo .env, requerirá reiniciar. ¿Continuar?")) {
      e.target.value = null;
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setIsImporting(true);

    try {
      const res = await fetch(`${API_URL}/config/import`, {
        method: "POST",
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        if (data.needs_restart) {
          setIsRestarting(true);
          // Empezar a hacer polling a /api/diagnostics/health para saber cuando reviva
          const pollInterval = setInterval(async () => {
            try {
              const ping = await fetch(`${API_URL}/diagnostics/health`, { signal: AbortSignal.timeout(2000) });
              if (ping.ok) {
                clearInterval(pollInterval);
                window.location.reload();
              }
            } catch (e) {
              // Aún no despierta, ignorar
            }
          }, 3000);
        } else {
          alert("Perfil importado y recargado con éxito.");
          fetchConfig(); // Refrescar UI con los nuevos estados
          setIsImporting(false);
        }
      } else {
        const errorData = await res.json();
        alert(`Error al importar: ${errorData.detail}`);
        setIsImporting(false);
      }
    } catch (error) {
      console.error(error);
      alert("Error de conexión al importar perfil.");
      setIsImporting(false);
    }
    
    e.target.value = null; // Reset input
  };

  const handleTestVoice = async (e) => {
    e.preventDefault();
    if (!testVoiceText.trim()) return;
    try {
      const res = await fetch(`${API_URL}/tts/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: testVoiceText })
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
      }
    } catch (e) {
      console.error("Error testing voice:", e);
    }
  };

  const handleSaveHardware = async (payload) => {
    try {
      await fetch(`${API_URL}/config/hardware`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if ("native_audio_output" in payload) setNativeAudioOutput(payload.native_audio_output);
      if ("robot_face_sync" in payload) setRobotFaceSync(payload.robot_face_sync);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      reconnectionAttempts: 5,
    });

    socket.on('connect', () => {
      setConnected(true);
      fetchCollections();
      fetchConfig();
      fetchCredentialsStatus();
    });
    socket.on('disconnect', () => setConnected(false));

    socket.on('telemetry_mic', (data) => {
      if (micEnergyTextRef.current) {
        micEnergyTextRef.current.textContent = data.energy;
      }
      if (micEnergyBarRef.current) {
        const scale = Math.min(1, data.energy / 2000);
        micEnergyBarRef.current.style.transform = `scaleX(${scale})`;
      }
    });
    socket.on('telemetry_vad', (data) => setVadActive(data.is_speaking));
    socket.on('telemetry_state', (data) => {
      if (data.state) setEngineState(data.state);
      if (data.session_active !== undefined) setSessionActive(data.session_active);
    });
    socket.on('telemetry_stt', (data) => setSttText(data.text));
    socket.on('telemetry_llm', (data) => {
      setLlmStream(prev => prev + data.token);
      if (data.provider) setLlmProvider(data.provider);
    });
    socket.on('telemetry_llm_clear', () => setLlmStream(""));
    socket.on('telemetry_tts', (data) => setTtsActive(data.is_playing));

    return () => socket.disconnect();
  }, []);

  // Fetch diagnostics on tab load
  useEffect(() => {
    if (activeTab === 'diagnostics' || activeTab === 'providers') {
      fetchDiagnostics();
    }
  }, [activeTab]);

  const tabs = [
    { id: 'home', label: 'Monitoreo', icon: Activity },
    { id: 'personality', label: 'Personalidad', icon: User },
    { id: 'wakeword', label: 'Wakeword', icon: Key },
    { id: 'voice', label: 'Voz', icon: Volume2 },
    { id: 'knowledge', label: 'RAG', icon: Database },
    { id: 'diagnostics', label: 'Diagnósticos', icon: CheckSquare },
    { id: 'providers', label: 'Proveedores (Tokens)', icon: CreditCard },
  ];

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <header className="bg-slate-900 border-b border-slate-800 p-4 md:p-6 flex flex-col md:flex-row items-center justify-between shadow-md gap-4">
        <div className="text-center md:text-left">
          <h1 className="text-2xl md:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
            KodaVox V2
          </h1>
          <p className="text-slate-400 mt-1 text-xs md:text-sm">Dashboard & Configuration Center</p>
        </div>
        <div className={`px-4 py-2 rounded-full font-medium flex items-center gap-2 text-sm ${connected ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`}></div>
          {connected ? 'Motor Conectado' : 'Esperando Motor...'}
        </div>
      </header>

      <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
        {/* Sidebar Navigation */}
        <aside className="w-full md:w-64 bg-slate-900/50 border-b md:border-b-0 md:border-r border-slate-800 p-4 flex flex-row md:flex-col gap-2 overflow-x-auto md:overflow-y-auto shrink-0 custom-scrollbar">
          {tabs.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive 
                    ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-sm' 
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 border border-transparent'
                }`}
              >
                <Icon size={18} className="shrink-0" />
                <span className="whitespace-nowrap">{tab.label}</span>
              </button>
            )
          })}
        </aside>

        {/* SETUP WIZARD / CREDENTIALS MODAL */}
        {showCredentialsModal && credentialsStatus && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-slate-900 w-full max-w-lg p-8 rounded-2xl border border-slate-700 shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-purple-500"></div>
              
              <div className="flex items-center gap-4 mb-6 shrink-0">
                <div className="p-3 bg-blue-500/20 text-blue-400 rounded-xl">
                  <Key size={28} />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">Configuración de APIs</h2>
                  <p className="text-sm text-slate-400">Introduce las llaves requeridas para los servicios en la nube que seleccionaste.</p>
                </div>
              </div>

              <div className="overflow-y-auto pr-2 custom-scrollbar flex-1 mb-4">
                <form id="credentials-form" onSubmit={handleSaveCredentials} className="space-y-5">
                  {credentialsStatus.llm_provider === 'openai' && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-300">OpenAI API Key <span className="text-red-400">*</span></label>
                      <input 
                        type="password" 
                        required
                        placeholder="sk-proj-..."
                        value={inputKeys.OPENAI_API_KEY}
                        onChange={e => setInputKeys({...inputKeys, OPENAI_API_KEY: e.target.value})}
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                  )}

                  {credentialsStatus.llm_provider === 'gemini' && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-300">Google Gemini API Key <span className="text-red-400">*</span></label>
                      <input 
                        type="password" 
                        required
                        placeholder="AIzaSy..."
                        value={inputKeys.GEMINI_API_KEY}
                        onChange={e => setInputKeys({...inputKeys, GEMINI_API_KEY: e.target.value})}
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                  )}

                  {(credentialsStatus.stt_provider === 'elevenlabs' || credentialsStatus.tts_provider === 'elevenlabs') && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-300">ElevenLabs API Key <span className="text-red-400">*</span></label>
                      <input 
                        type="password" 
                        required
                        placeholder="sk_..."
                        value={inputKeys.ELEVENLABS_API_KEY}
                        onChange={e => setInputKeys({...inputKeys, ELEVENLABS_API_KEY: e.target.value})}
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                  )}
                </form>

                <div className="mt-8 border-t border-slate-800 pt-6">
                  <div className="flex items-center gap-2 mb-3">
                    <DownloadCloud size={16} className="text-indigo-400" />
                    <h3 className="text-sm font-semibold text-slate-300">¿Tienes un Respaldo?</h3>
                  </div>
                  <p className="text-xs text-slate-500 mb-4">Si exportaste tus credenciales y configuración previamente, puedes importarlas directamente aquí.</p>
                  <div className="relative w-full">
                    <input type="file" accept=".zip" id="import-profile-modal" className="hidden" onChange={handleImportProfile} disabled={isImporting} />
                    <label 
                      htmlFor="import-profile-modal" 
                      className={`w-full ${isImporting ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/50 cursor-not-allowed' : 'bg-slate-950 text-indigo-400 hover:bg-indigo-500/10 border-slate-700 hover:border-indigo-500 cursor-pointer'} px-4 py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-colors border border-dashed`}
                    >
                      {isImporting ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                      {isImporting ? "Procesando Paquete..." : "Importar Perfil Completo (.zip)"}
                    </label>
                  </div>
                </div>
              </div>

              <div className="pt-4 flex gap-3 shrink-0 mt-auto border-t border-slate-800/50">
                <button 
                  type="submit" 
                  form="credentials-form"
                  disabled={isSavingKeys || isImporting}
                  className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isSavingKeys ? <Loader2 size={18} className="animate-spin" /> : <CheckSquare size={18} />}
                  {isSavingKeys ? 'Guardando...' : 'Guardar Llaves'}
                </button>
                <button 
                  type="button" 
                  onClick={() => setShowCredentialsModal(false)}
                  disabled={isImporting}
                  className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-xl transition-colors disabled:opacity-50"
                >
                  Omitir
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8 text-slate-200">
          
          {/* TAB: HOME */}
          {activeTab === 'home' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              {/* VAD & Micrófono */}
              <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 shadow-lg">
                <div className="flex items-center gap-3 mb-6">
                  <div className={`p-3 rounded-lg ${vadActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-400'}`}>
                    {vadActive ? <Mic size={24} /> : <MicOff size={24} />}
                  </div>
                  <h2 className="text-xl font-semibold">Voice Activity (VAD)</h2>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm text-slate-400 mb-1">
                      <span>Energía (Mic)</span>
                      <span ref={micEnergyTextRef}>0</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-3 overflow-hidden">
                      <div 
                        ref={micEnergyBarRef}
                        className="w-full bg-blue-500 h-3 origin-left transition-transform duration-75"
                        style={{ transform: 'scaleX(0)' }}
                      ></div>
                    </div>
                  </div>
                  <div className={`p-4 rounded-lg text-center font-medium transition-colors ${vadActive ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400 border border-slate-700'}`}>
                    {vadActive ? 'Usuario Hablando...' : 'Silencio Detectado'}
                  </div>
                </div>
              </div>

              {/* STT (Whisper) */}
              <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 shadow-lg lg:col-span-2">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-3 rounded-lg bg-blue-500/20 text-blue-400">
                    <MessageSquare size={24} />
                  </div>
                  <h2 className="text-xl font-semibold">Transcripción (Whisper)</h2>
                </div>
                <div className="bg-slate-950 rounded-lg p-4 min-h-[120px] font-mono text-slate-300 border border-slate-800/50">
                  {sttText || <span className="text-slate-600">Esperando entrada de voz...</span>}
                </div>
              </div>

              {/* LLM */}
              <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 shadow-lg lg:col-span-2">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-3 rounded-lg bg-purple-500/20 text-purple-400">
                    <Cpu size={24} />
                  </div>
                  <h2 className="text-xl font-semibold">
                    Respuesta LLM {llmProvider ? `(${llmProvider.toUpperCase()})` : ''}
                  </h2>
                </div>
                <div className="bg-slate-950 rounded-lg p-4 min-h-[200px] font-mono text-slate-300 border border-slate-800/50 whitespace-pre-wrap">
                  {llmStream || <span className="text-slate-600">Esperando procesamiento...</span>}
                </div>
              </div>

              {/* TTS */}
              <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 shadow-lg">
                <div className="flex items-center gap-3 mb-6">
                  <div className={`p-3 rounded-lg ${ttsActive ? 'bg-orange-500/20 text-orange-400 animate-pulse' : 'bg-slate-800 text-slate-400'}`}>
                    <Volume2 size={24} />
                  </div>
                  <h2 className="text-xl font-semibold">Síntesis (TTS)</h2>
                </div>
                <div className={`p-6 rounded-lg text-center font-medium transition-colors ${ttsActive ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-slate-800 text-slate-400 border border-slate-700'}`}>
                  {ttsActive ? 'Sintetizando y Hablando...' : 'En Espera'}
                </div>
              </div>
            </div>
          )}

          {/* TAB: PERSONALITY */}
          {activeTab === 'personality' && (
            <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-slate-900 p-8 rounded-xl border border-slate-800 shadow-lg flex flex-col min-h-[500px]">
                <div className="flex items-center gap-4 mb-6">
                  <div className="p-4 rounded-xl bg-pink-500/10 text-pink-400 border border-pink-500/20">
                    <User size={32} />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold">Personalidad Base (System Prompt)</h2>
                    <p className="text-slate-400 text-sm mt-1">Define cómo piensa, habla y se comporta KodaVox.</p>
                  </div>
                </div>
                
                <form onSubmit={handleSavePersonality} className="flex flex-col flex-1 space-y-6">
                  <div className="flex flex-col">
                    <label className="text-sm font-medium text-slate-300 mb-2">Instrucciones del Sistema (System Prompt)</label>
                    <textarea
                      className="bg-slate-950 border border-slate-800 rounded-xl p-5 text-slate-200 outline-none focus:border-pink-500 focus:ring-1 focus:ring-pink-500/50 min-h-[140px] resize-y transition-all"
                      value={personalityPrompt}
                      onChange={(e) => setPersonalityPrompt(e.target.value)}
                      placeholder="Ej: Eres un asistente virtual amigable, experto en ciencia y muy breve..."
                    />
                  </div>

                  {/* Parámetros de Comportamiento e Inteligencia */}
                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 space-y-6">
                    <h3 className="font-semibold text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
                      <Cpu size={18} className="text-pink-400" /> Parámetros de Creatividad y Respuestas RAG
                    </h3>

                    {/* Temperatura LLM */}
                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <label className="text-sm font-medium text-slate-300">
                          Temperatura LLM (Creatividad): <span className="text-pink-400 font-mono font-bold">{llmTemperature.toFixed(2)}</span>
                        </label>
                        <span className="text-xs px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-400">
                          {llmTemperature < 0.3 ? '🎯 Factual & Estricto' : llmTemperature > 0.7 ? '🎨 Creativo & Variado' : '⚖️ Equilibrado'}
                        </span>
                      </div>
                      <input 
                        type="range" min="0.0" max="1.0" step="0.05"
                        value={llmTemperature}
                        onChange={(e) => setLlmTemperature(parseFloat(e.target.value))}
                        className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-pink-500"
                      />
                      <div className="flex justify-between text-[11px] text-slate-500">
                        <span>0.0 (Factual / Manuales)</span>
                        <span>0.5 (Conversación Natural)</span>
                        <span>1.0 (Máxima Invención/Estilo)</span>
                      </div>
                    </div>

                    {/* Modo RAG Estricto */}
                    <div className="flex items-center justify-between pt-3 border-t border-slate-800/60">
                      <div>
                        <h4 className="font-medium text-slate-200 text-sm">Modo RAG Estricto (Solo Base de Conocimiento)</h4>
                        <p className="text-xs text-slate-400 mt-1 max-w-xl">
                          Si está activo, el LLM responderá **únicamente** usando datos recuperados de tus colecciones RAG, evitando apoyarse en su conocimiento general o inventar respuestas fuera del contexto.
                        </p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer ml-4">
                        <input 
                          type="checkbox" 
                          className="sr-only peer" 
                          checked={ragStrictMode} 
                          onChange={(e) => setRagStrictMode(e.target.checked)} 
                        />
                        <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-pink-500"></div>
                      </label>
                    </div>
                  </div>

                  <button type="submit" className="bg-pink-600 hover:bg-pink-500 text-white px-6 py-3 rounded-xl font-medium transition-colors self-end flex items-center gap-2 shadow-lg shadow-pink-500/20">
                    Guardar Personalidad & Parámetros
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* TAB: WAKEWORD */}
          {activeTab === 'wakeword' && (
            <div className="max-w-2xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-slate-900 p-8 rounded-xl border border-slate-800 shadow-lg flex flex-col">
                <div className="flex items-center gap-4 mb-8">
                  <div className="p-4 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    <Key size={32} />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold">Configuración de Wakeword</h2>
                    <p className="text-slate-400 text-sm mt-1">Palabra mágica de activación y tiempos de sesión.</p>
                  </div>
                </div>
                
                <form onSubmit={handleSaveWakeWord} className="flex flex-col gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-300 ml-1">Palabra de Activación</label>
                    <div className="bg-slate-950 border border-slate-800 rounded-xl flex items-center px-4 focus-within:border-amber-500 transition-colors">
                      <input 
                        type="text" 
                        value={wakeWord}
                        onChange={(e) => setWakeWord(e.target.value)}
                        className="bg-transparent border-none outline-none text-slate-200 py-3 w-full"
                        placeholder="ej: kodavox"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-300 ml-1">Temporizador de Sesión (Segundos)</label>
                    <div className="bg-slate-950 border border-slate-800 rounded-xl flex items-center px-4 focus-within:border-amber-500 transition-colors w-full sm:w-1/2">
                      <input 
                        type="number" 
                        value={wakeTimeout}
                        onChange={(e) => setWakeTimeout(e.target.value)}
                        className="bg-transparent border-none outline-none text-slate-200 py-3 w-full"
                        placeholder="10"
                        min="1"
                        max="60"
                      />
                    </div>
                    <p className="text-xs text-slate-500 ml-1 mt-1">Tiempo que KodaVox te escuchará después de hablar antes de volver a dormir.</p>
                  </div>

                  <div className="h-px bg-slate-800/80 my-2"></div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold text-slate-200 text-lg">Calibración de Detección de Voz (VAD & Audio)</h3>
                      <span className="text-[10px] uppercase font-bold tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded-full">
                        Afecta: Todos los proveedores (Whisper & ElevenLabs)
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-slate-950 p-5 rounded-xl border border-slate-800">
                      <div>
                        <div className="flex justify-between text-xs mb-2">
                          <span className="text-slate-300 font-medium">Sensibilidad VAD (Threshold)</span>
                          <span className="text-amber-400 font-mono bg-amber-500/10 px-2 py-0.5 rounded">{vadThreshold.toFixed(2)}</span>
                        </div>
                        <input type="range" min="0.1" max="0.9" step="0.05" value={vadThreshold} onChange={(e) => setVadThreshold(parseFloat(e.target.value))} className="w-full accent-amber-500 mb-1" />
                        <p className="text-[11px] text-slate-400">Cuán fuerte debe sonar la voz respecto al ruido ambiente para activarse.</p>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs mb-2">
                          <span className="text-slate-300 font-medium">Silencio de Fin de Frase (Seg)</span>
                          <span className="text-amber-400 font-mono bg-amber-500/10 px-2 py-0.5 rounded">{vadEndSilence.toFixed(2)}s</span>
                        </div>
                        <input type="range" min="0.3" max="2.0" step="0.05" value={vadEndSilence} onChange={(e) => setVadEndSilence(parseFloat(e.target.value))} className="w-full accent-amber-500 mb-1" />
                        <p className="text-[11px] text-slate-400">Segundos de silencio para asumir que terminaste de hablar y procesar la respuesta.</p>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs mb-2">
                          <span className="text-slate-300 font-medium">Duración Mínima de Voz (Seg)</span>
                          <span className="text-amber-400 font-mono bg-amber-500/10 px-2 py-0.5 rounded">{sttMinSpeech.toFixed(2)}s</span>
                        </div>
                        <input type="range" min="0.1" max="1.0" step="0.05" value={sttMinSpeech} onChange={(e) => setSttMinSpeech(parseFloat(e.target.value))} className="w-full accent-amber-500 mb-1" />
                        <p className="text-[11px] text-slate-400">Filtra ruidos o estornudos muy breves para no hacer llamadas STT innecesarias.</p>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs mb-2">
                          <span className="text-slate-300 font-medium">Pre-Padding de Audio (Seg)</span>
                          <span className="text-amber-400 font-mono bg-amber-500/10 px-2 py-0.5 rounded">{vadPrePadding.toFixed(2)}s</span>
                        </div>
                        <input type="range" min="0.05" max="0.5" step="0.05" value={vadPrePadding} onChange={(e) => setVadPrePadding(parseFloat(e.target.value))} className="w-full accent-amber-500 mb-1" />
                        <p className="text-[11px] text-slate-400">Milisegundos acumulados antes del habla para evitar recortar la primera palabra.</p>
                      </div>
                    </div>
                  </div>

                  <button type="submit" className="bg-amber-600 hover:bg-amber-500 text-white px-6 py-3 rounded-xl font-medium transition-colors self-end mt-4 shadow-lg shadow-amber-500/20">
                    Guardar Configuración de Wakeword y VAD
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* TAB: VOICE */}
          {activeTab === 'voice' && (
            <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-slate-900 p-8 rounded-xl border border-slate-800 shadow-lg flex flex-col">
                <div className="flex items-center gap-4 mb-8">
                  <div className="p-4 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    <Volume2 size={32} />
                  </div>
                  <div className="flex-1">
                    <h2 className="text-2xl font-bold">Catálogo de Voces ElevenLabs</h2>
                    <p className="text-slate-400 text-sm mt-1">Selecciona la voz activa o añade nuevos modelos sintéticos.</p>
                  </div>
                </div>

                <div className="mb-8 bg-slate-950/50 p-6 rounded-xl border border-slate-800/50 flex flex-col gap-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-lg text-slate-200">Voz Activa Actual</h3>
                      <p className="text-slate-400 text-sm">Esta es la voz con la que responderá KodaVox.</p>
                    </div>
                    <select 
                      className="bg-slate-900 border border-indigo-500/50 rounded-xl px-4 py-2 text-slate-200 outline-none focus:border-indigo-400 shadow-lg shadow-indigo-500/10 min-w-[200px]"
                      value={activeVoiceId}
                      onChange={handleSetActiveVoice}
                    >
                      {elevenlabsVoices.map(v => (
                        <option key={v.id} value={v.id}>{v.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="h-px bg-slate-800/50 w-full"></div>

                  <div>
                    <h3 className="font-semibold mb-2 text-slate-300 flex items-center gap-2 text-sm">
                      <MessageSquare size={16} className="text-indigo-400" /> Probar Voz Seleccionada
                    </h3>
                    <form onSubmit={handleTestVoice} className="flex gap-4">
                      <input 
                        type="text" 
                        value={testVoiceText}
                        onChange={(e) => setTestVoiceText(e.target.value)}
                        className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="Escribe algo para probar la voz..."
                      />
                      <button 
                        type="submit"
                        disabled={ttsActive}
                        className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-400 px-6 py-2 rounded-lg transition-colors text-white text-sm font-medium shadow-lg shadow-indigo-500/20 whitespace-nowrap"
                      >
                        {ttsActive ? 'Hablando...' : 'Escuchar Voz'}
                      </button>
                    </form>
                  </div>
                </div>

                <div className="mb-8 bg-slate-950 p-6 rounded-xl border border-slate-800 shadow-inner">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-slate-300">Personalización de Emoción y Estilo (ElevenLabs)</h3>
                        <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${ttsProvider === 'elevenlabs' ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' : 'bg-slate-800 text-slate-500 border-slate-700'}`}>
                          {ttsProvider === 'elevenlabs' ? 'Activo Actualmente' : 'Afecta solo a ElevenLabs'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">Ajusta cómo la IA interpreta y pronuncia las emociones de la voz en la nube.</p>
                    </div>
                    <button onClick={handleSaveVoiceSettings} className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-4 py-2 rounded-lg transition-colors border border-slate-700 shadow-sm">
                      Guardar Ajustes
                    </button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div>
                      <div className="flex justify-between text-xs mb-2">
                        <span className="text-slate-400 font-medium">Estabilidad</span>
                        <span className="text-indigo-400 font-mono bg-indigo-500/10 px-2 rounded">{voiceStability.toFixed(2)}</span>
                      </div>
                      <input type="range" min="0" max="1" step="0.01" value={voiceStability} onChange={(e) => setVoiceStability(parseFloat(e.target.value))} className="w-full accent-indigo-500 mb-1" />
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>Emotivo / Variable</span>
                        <span>Monótono / Fijo</span>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-2">
                        <span className="text-slate-400 font-medium">Similitud (Similarity Boost)</span>
                        <span className="text-indigo-400 font-mono bg-indigo-500/10 px-2 rounded">{voiceSimilarity.toFixed(2)}</span>
                      </div>
                      <input type="range" min="0" max="1" step="0.01" value={voiceSimilarity} onChange={(e) => setVoiceSimilarity(parseFloat(e.target.value))} className="w-full accent-indigo-500 mb-1" />
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>Voz Genérica</span>
                        <span>Clon Original</span>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-2">
                        <span className="text-slate-400 font-medium">Exageración de Estilo</span>
                        <span className="text-indigo-400 font-mono bg-indigo-500/10 px-2 rounded">{voiceStyle.toFixed(2)}</span>
                      </div>
                      <input type="range" min="0" max="1" step="0.01" value={voiceStyle} onChange={(e) => setVoiceStyle(parseFloat(e.target.value))} className="w-full accent-indigo-500 mb-1" />
                    </div>
                    <div className="flex items-center justify-between bg-slate-900 px-4 py-3 rounded-xl border border-slate-800 h-[60px]">
                      <div>
                        <span className="text-sm font-medium text-slate-300 block">Speaker Boost</span>
                        <span className="text-[10px] text-slate-500">Mejora la calidad del clon.</span>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" className="sr-only peer" checked={voiceSpeakerBoost} onChange={(e) => setVoiceSpeakerBoost(e.target.checked)} />
                        <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-300 after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-500 border border-slate-700"></div>
                      </label>
                    </div>
                  </div>
                </div>

                <div className="mb-8 bg-slate-950 p-6 rounded-xl border border-slate-800 shadow-inner">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-slate-300">Calibración de Piper TTS (Motor Local On-Device)</h3>
                        <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${ttsProvider === 'piper' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-slate-800 text-slate-500 border-slate-700'}`}>
                          {ttsProvider === 'piper' ? 'Activo Actualmente' : 'Afecta solo a Piper Local'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">Ajusta la rapidez y expresividad sintética del modelo local `.onnx` cuando se usa Piper.</p>
                    </div>
                    <button onClick={handleSaveWakeWord} className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-4 py-2 rounded-lg transition-colors border border-slate-700 shadow-sm">
                      Guardar Ajustes Piper
                    </button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div>
                      <div className="flex justify-between text-xs mb-2">
                        <span className="text-slate-400 font-medium">Velocidad / Largo de Habla (Length Scale)</span>
                        <span className="text-emerald-400 font-mono bg-emerald-500/10 px-2 rounded">{piperLengthScale.toFixed(2)}</span>
                      </div>
                      <input type="range" min="0.5" max="1.5" step="0.05" value={piperLengthScale} onChange={(e) => setPiperLengthScale(parseFloat(e.target.value))} className="w-full accent-emerald-500 mb-1" />
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>Habla Rápida (ej. 0.85)</span>
                        <span>Habla Lenta (ej. 1.20)</span>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-2">
                        <span className="text-slate-400 font-medium">Variabilidad / Expresividad (Noise Scale)</span>
                        <span className="text-emerald-400 font-mono bg-emerald-500/10 px-2 rounded">{piperNoiseScale.toFixed(2)}</span>
                      </div>
                      <input type="range" min="0.1" max="1.2" step="0.05" value={piperNoiseScale} onChange={(e) => setPiperNoiseScale(parseFloat(e.target.value))} className="w-full accent-emerald-500 mb-1" />
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>Voz Estable</span>
                        <span>Voz Expresiva</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 h-fit">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-slate-300">Añadir Voz</h3>
                      <div className="flex bg-slate-900 rounded-lg p-1 border border-slate-800">
                        <button
                          onClick={() => setVoiceAddMode("id")}
                          className={`px-3 py-1 text-xs rounded-md transition-colors ${voiceAddMode === "id" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"}`}
                        >
                          Por ID
                        </button>
                        <button
                          onClick={() => setVoiceAddMode("clone")}
                          className={`px-3 py-1 text-xs rounded-md transition-colors ${voiceAddMode === "clone" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"}`}
                        >
                          Clonar
                        </button>
                      </div>
                    </div>

                    {voiceAddMode === "id" ? (
                      <form onSubmit={handleAddVoice} className="flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="space-y-1">
                          <label className="text-xs text-slate-500 ml-1">Nombre Descriptivo</label>
                          <input 
                            type="text" 
                            placeholder="ej. Drew (Narrador)" 
                            value={newVoiceName}
                            onChange={(e) => setNewVoiceName(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-slate-500 ml-1">ID de ElevenLabs</label>
                          <input 
                            type="text" 
                            placeholder="ej. 21m00Tcm4TlvDq8ikWAM" 
                            value={newVoiceId}
                            onChange={(e) => setNewVoiceId(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                        <button 
                          type="submit"
                          className="bg-indigo-600 hover:bg-indigo-500 px-4 py-2.5 rounded-lg transition-colors text-white font-medium flex items-center justify-center gap-2 mt-2"
                        >
                          <Plus size={18} /> Registrar Voz
                        </button>
                      </form>
                    ) : (
                      <form onSubmit={handleCloneVoice} className="flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="space-y-1">
                          <label className="text-xs text-slate-500 ml-1">Nombre para la Nueva Voz</label>
                          <input 
                            type="text" 
                            placeholder="ej. Mi Clon de Voz" 
                            value={cloneVoiceName}
                            onChange={(e) => setCloneVoiceName(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                        
                        <div className="space-y-1">
                          <label className="text-xs text-slate-500 ml-1">Muestra de Audio (.mp3, .wav)</label>
                          <div className="flex gap-2">
                            <input 
                              type="file" 
                              accept="audio/mpeg,audio/wav"
                              onChange={(e) => setCloneFile(e.target.files[0])}
                              className="hidden"
                              id="clone-file-upload"
                            />
                            <label htmlFor="clone-file-upload" className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-400 hover:text-slate-200 cursor-pointer flex items-center gap-2 hover:bg-slate-800 transition-colors">
                              <UploadCloud size={16} /> 
                              {cloneFile ? cloneFile.name : "Subir Archivo"}
                            </label>
                            
                            <button
                              type="button"
                              onClick={isRecording ? stopRecording : startRecording}
                              className={`px-4 py-2.5 rounded-lg flex items-center justify-center transition-colors border ${isRecording ? 'bg-red-500/10 text-red-500 border-red-500/50 hover:bg-red-500/20' : 'bg-slate-900 text-slate-400 border-slate-800 hover:bg-slate-800 hover:text-slate-200'}`}
                              title={isRecording ? "Detener Grabación" : "Grabar desde Micrófono"}
                            >
                              {isRecording ? <MicOff size={16} className="animate-pulse" /> : <Mic size={16} />}
                            </button>
                          </div>
                          {isRecording && <p className="text-[10px] text-red-400 animate-pulse text-right">Grabando... (Click para detener)</p>}
                        </div>
                        
                        <button 
                          type="submit"
                          disabled={isCloning || !cloneFile || !cloneVoiceName}
                          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 px-4 py-2.5 rounded-lg transition-colors text-white font-medium flex items-center justify-center gap-2 mt-2"
                        >
                          {isCloning ? "Clonando Voz..." : "Crear Voz"}
                        </button>
                      </form>
                    )}
                  </div>

                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 flex flex-col">
                    <h3 className="font-semibold mb-4 text-slate-300">Voces Registradas</h3>
                    <div className="space-y-3 max-h-[280px] overflow-y-auto pr-2 custom-scrollbar">
                      {elevenlabsVoices.map(v => (
                        <div key={v.id} className={`flex items-center justify-between p-3 rounded-lg border ${v.id === activeVoiceId ? 'bg-indigo-500/10 border-indigo-500/50' : 'bg-slate-900 border-slate-800'}`}>
                          <div>
                            <div className="text-sm font-medium text-slate-200">{v.name} {v.id === activeVoiceId && <span className="text-[10px] uppercase tracking-wider font-bold bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded ml-2">Activa</span>}</div>
                            <div className="text-xs text-slate-500 font-mono mt-0.5">{v.id}</div>
                          </div>
                          <button 
                            onClick={() => handleDeleteVoice(v.id)}
                            className="text-red-400 hover:bg-red-500/10 p-2 rounded-lg transition-colors"
                            disabled={elevenlabsVoices.length <= 1}
                            title="Eliminar Voz"
                          >
                            <Trash size={16} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: KNOWLEDGE BASE (RAG) */}
          {activeTab === 'knowledge' && (
            <div className="max-w-5xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-slate-900 p-8 rounded-xl border border-slate-800 shadow-lg flex flex-col">
                <div className="flex items-center justify-between mb-8 pb-6 border-b border-slate-800">
                  <div className="flex items-center gap-4">
                    <div className="p-4 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
                      <Database size={32} />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold">Base de Conocimientos (RAG)</h2>
                      <p className="text-slate-400 text-sm mt-1">Inyecta documentos y datos para darle memoria a largo plazo a KodaVox.</p>
                    </div>
                  </div>
                  
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex items-center gap-4 shadow-inner">
                    <div>
                      <div className="text-xs text-slate-500 font-medium mb-1 uppercase tracking-wider">Cerebro Activo</div>
                      <select 
                        className="bg-slate-900 border border-teal-500/30 rounded-lg px-4 py-2 text-slate-200 outline-none focus:border-teal-400 text-sm font-medium min-w-[200px]"
                        value={activeCollection}
                        onChange={handleSetActive}
                      >
                        <option value="">-- Ninguno (Desactivado) --</option>
                        {collections.map(c => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800">
                    <h3 className="font-semibold text-slate-300 mb-5 flex items-center gap-2">
                      <Database size={18} className="text-teal-400" /> Administrar Colecciones
                    </h3>
                    
                    <form onSubmit={handleCreateCollection} className="flex gap-2 mb-6">
                      <input 
                        type="text" 
                        placeholder="Nombre de la nueva colección..." 
                        value={newCollectionName}
                        onChange={(e) => setNewCollectionName(e.target.value)}
                        className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
                      />
                      <button 
                        type="submit"
                        className="bg-teal-600 hover:bg-teal-500 px-4 py-2.5 rounded-lg transition-colors text-white font-medium"
                      >
                        Crear
                      </button>
                    </form>

                    <div className="space-y-2 max-h-[250px] overflow-y-auto pr-2">
                      {collections.map(c => (
                        <div key={c} className={`flex items-center justify-between p-3 rounded-lg border ${c === activeCollection ? 'bg-teal-500/10 border-teal-500/30' : 'bg-slate-900 border-slate-800'}`}>
                          <span className="text-sm font-medium text-slate-300">{c}</span>
                          <button 
                            onClick={() => handleDeleteCollection(c)}
                            className="text-red-400 hover:bg-red-500/10 p-1.5 rounded-md transition-colors"
                          >
                            <Trash size={16} />
                          </button>
                        </div>
                      ))}
                      {collections.length === 0 && (
                        <div className="text-center py-10 bg-slate-900/50 rounded-lg border border-dashed border-slate-800">
                          <p className="text-sm text-slate-500">No hay colecciones creadas.</p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 flex flex-col">
                    <h3 className="font-semibold text-slate-300 mb-5 flex items-center gap-2">
                      <Upload size={18} className="text-teal-400" /> Subir Documento a Colección
                    </h3>
                    
                    <form onSubmit={handleUpload} className="flex flex-col flex-1 gap-6">
                      {collections.length === 0 ? (
                        <div className="flex-1 flex items-center justify-center text-center p-6 bg-amber-500/5 border border-amber-500/20 rounded-lg">
                          <p className="text-sm text-amber-400/80">Debes crear al menos una colección en el panel izquierdo antes de poder subir documentos.</p>
                        </div>
                      ) : (
                        <>
                          <div className="space-y-2">
                            <label className="text-xs text-slate-500 font-medium">Colección de Destino:</label>
                            <select 
                              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-4 py-3 text-sm text-slate-200 outline-none focus:border-teal-500"
                              value={activeCollection || collections[0]}
                              onChange={(e) => setActiveCollection(e.target.value)}
                            >
                              {collections.map(c => (
                                <option key={c} value={c}>{c}</option>
                              ))}
                            </select>
                          </div>
                          
                          <div className="space-y-2">
                            <label className="text-xs text-slate-500 font-medium">Archivo (.txt, .md, .pdf, .json, .csv):</label>
                            <div className="bg-slate-900 border border-slate-800 border-dashed rounded-lg p-4 flex flex-col items-center justify-center hover:border-teal-500/50 transition-colors">
                              <input 
                                type="file" 
                                accept=".txt,.md,.pdf,.json,.csv"
                                onChange={(e) => setUploadFile(e.target.files[0])}
                                className="block w-full text-sm text-slate-400
                                  file:mr-4 file:py-2 file:px-4
                                  file:rounded-lg file:border-0
                                  file:text-sm file:font-semibold
                                  file:bg-teal-500/10 file:text-teal-400
                                  hover:file:bg-teal-500/20 cursor-pointer"
                              />
                            </div>
                          </div>

                          <div className="mt-auto pt-4">
                            <button 
                              type="submit" 
                              disabled={isUploading || !uploadFile}
                              className="w-full bg-teal-600 hover:bg-teal-500 text-white px-4 py-3 rounded-xl text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-teal-500/20"
                            >
                              {isUploading ? 'Procesando e Indexando...' : 'Subir e Indexar Documento'}
                            </button>
                          </div>
                        </>
                      )}
                    </form>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: DIAGNOSTICS */}
          {activeTab === 'diagnostics' && (
            <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-slate-900 p-8 rounded-xl border border-slate-800 shadow-lg">
                <div className="flex items-center gap-4 mb-8">
                  <div className="p-4 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    <CheckSquare size={32} />
                  </div>
                  <div className="flex-1">
                    <h2 className="text-2xl font-bold">Diagnóstico de Módulos</h2>
                    <p className="text-slate-400 text-sm mt-1">Verifica el estado interno de los componentes del motor KodaVox.</p>
                  </div>
                  <button 
                    onClick={fetchDiagnostics}
                    disabled={isCheckingHealth}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
                  >
                    {isCheckingHealth ? 'Chequeando...' : 'Actualizar Estado'}
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { label: `Modelo STT (${healthStatus?.stt_provider === 'elevenlabs' ? 'ElevenLabs Scribe Cloud' : 'Whisper GPU Local'})`, status: healthStatus?.stt },
                    { label: "Modelo VAD (Silero)", status: healthStatus?.vad },
                    { label: "Proveedor LLM", status: healthStatus?.llm },
                    { label: "Conexión RAG (Chroma)", status: healthStatus?.rag },
                    { label: "Micrófono (Captura PyAudio)", status: healthStatus?.microphone_active },
                  ].map((item, idx) => (
                    <div key={idx} className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex items-center justify-between">
                      <span className="font-medium text-slate-300">{item.label}</span>
                      {item.status === undefined ? (
                        <span className="text-slate-500 text-sm">Cargando...</span>
                      ) : item.status ? (
                        <span className="bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">OK</span>
                      ) : (
                        <span className="bg-red-500/20 text-red-400 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">Falla</span>
                      )}
                    </div>
                  ))}
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex items-center justify-between md:col-span-2">
                    <span className="font-medium text-slate-300">Estado del Motor en Tiempo Real</span>
                    <div className="flex gap-2">
                      {engineState === 'wakeword_detected' && (
                        <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse">
                          ⚡ Wakeword Detectada
                        </span>
                      )}
                      <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${sessionActive ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-slate-800 text-slate-500'}`}>
                        {sessionActive ? 'Sesión Activa' : 'Standby / Esperando Wakeword'}
                      </span>
                      <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${vadActive ? 'bg-orange-500/20 text-orange-400' : 'bg-slate-800 text-slate-500'}`}>
                        {vadActive ? 'Usuario Hablando' : 'Silencio'}
                      </span>
                      <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${llmStream || ttsActive || engineState === 'processing' ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-800 text-slate-500'}`}>
                        {ttsActive ? 'Hablando (TTS)' : llmStream || engineState === 'processing' ? 'Generando Respuesta' : 'Idle'}
                      </span>
                    </div>
                  </div>
                </div>

                <h3 className="font-semibold text-lg text-slate-200 mt-8 mb-4 border-b border-slate-800 pb-2">Configuración de Hardware (Headless Mode)</h3>
                <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 flex flex-col gap-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-slate-200">Salida de Audio Nativa</h4>
                      <p className="text-sm text-slate-500 mt-1">Si se desactiva, el motor no usará las bocinas físicas del servidor.</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" checked={nativeAudioOutput} onChange={(e) => handleSaveHardware({native_audio_output: e.target.checked})} />
                      <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500"></div>
                    </label>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-slate-200">Sincronización de Estados (Robot Face)</h4>
                      <p className="text-sm text-slate-500 mt-1">Conecta KodaVox al servidor WebSocket existente en el puerto 8760 para inyectar comandos de animaciones faciales (Escuchando, Pensando).</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" checked={robotFaceSync} onChange={(e) => handleSaveHardware({robot_face_sync: e.target.checked})} />
                      <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500"></div>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: PROVIDERS & USAGE */}
          {activeTab === 'providers' && (
            <div className="max-w-5xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-slate-900 p-8 rounded-xl border border-slate-800 shadow-lg mb-8">
                <div className="flex items-center gap-4 mb-8">
                  <div className="p-4 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CreditCard size={32} />
                  </div>
                  <div className="flex-1">
                    <h2 className="text-2xl font-bold">Proveedores y Consumo</h2>
                    <p className="text-slate-400 text-sm mt-1">Verifica el estado de tus APIs y el consumo de tokens diario.</p>
                  </div>
                  <button 
                    onClick={fetchDiagnostics}
                    disabled={isCheckingHealth}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
                  >
                    Actualizar
                  </button>
                </div>

                <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                  <h3 className="font-semibold text-lg text-slate-200">Estado de APIs</h3>
                  <button 
                    onClick={() => setShowCredentialsModal(true)}
                    className="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors"
                  >
                    <Key size={14} /> Reconfigurar Llaves
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                  {/* OpenAI */}
                  {(!credentialsStatus || credentialsStatus.llm_provider === 'openai') && (
                    <div className="bg-slate-950 p-5 rounded-xl border border-slate-800 flex flex-col items-center text-center">
                      <h4 className="font-semibold text-slate-300 mb-2">OpenAI</h4>
                      {providersStatus?.openai?.status === 'ok' ? (
                        <span className="text-emerald-400 font-medium">Conectado (API Key Válida)</span>
                      ) : providersStatus?.openai?.status === 'missing_key' ? (
                        <span className="text-slate-500">No Configurado</span>
                      ) : (
                        <span className="text-red-400 font-medium">Error: {providersStatus?.openai?.status}</span>
                      )}
                    </div>
                  )}
                  {/* Gemini */}
                  {(!credentialsStatus || credentialsStatus.llm_provider === 'gemini') && (
                    <div className="bg-slate-950 p-5 rounded-xl border border-slate-800 flex flex-col items-center text-center">
                      <h4 className="font-semibold text-slate-300 mb-2">Google Gemini</h4>
                      {providersStatus?.gemini?.status === 'ok' ? (
                        <span className="text-emerald-400 font-medium">Conectado (API Key Válida)</span>
                      ) : providersStatus?.gemini?.status === 'missing_key' ? (
                        <span className="text-slate-500">No Configurado</span>
                      ) : (
                        <span className="text-red-400 font-medium">Error: {providersStatus?.gemini?.status}</span>
                      )}
                    </div>
                  )}
                  {/* ElevenLabs */}
                  {(!credentialsStatus || credentialsStatus.stt_provider === 'elevenlabs' || credentialsStatus.tts_provider === 'elevenlabs') && (
                    <div className="bg-slate-950 p-5 rounded-xl border border-slate-800 flex flex-col items-center text-center">
                      <h4 className="font-semibold text-slate-300 mb-2">ElevenLabs</h4>
                      {providersStatus?.elevenlabs?.status === 'ok' ? (
                        <span className="text-emerald-400 font-medium">Conectado ({providersStatus.elevenlabs.status_tier})</span>
                      ) : providersStatus?.elevenlabs?.status === 'missing_key' ? (
                        <span className="text-slate-500">No Configurado</span>
                      ) : providersStatus?.elevenlabs?.status === 'invalid_key' ? (
                        <span className="text-red-400 font-medium">Llave de API Inválida (401)</span>
                      ) : (
                        <span className="text-red-400 font-medium">
                          Error de Conexión {providersStatus?.elevenlabs?.code ? `(${providersStatus.elevenlabs.code})` : ''}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <h3 className="font-semibold text-lg text-slate-200 mb-4 border-b border-slate-800 pb-2">Configuración de Costos ($ USD por 1 Millón)</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col gap-2">
                    <label className="text-xs text-slate-400 font-medium">Costo OpenAI (por 1M tokens)</label>
                    <input 
                      type="number" step="0.001"
                      className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                      value={costRates.openai}
                      onChange={(e) => saveCostRates({...costRates, openai: parseFloat(e.target.value) || 0})}
                    />
                  </div>
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col gap-2">
                    <label className="text-xs text-slate-400 font-medium">Costo Gemini (por 1M tokens)</label>
                    <input 
                      type="number" step="0.001"
                      className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                      value={costRates.gemini}
                      onChange={(e) => saveCostRates({...costRates, gemini: parseFloat(e.target.value) || 0})}
                    />
                  </div>
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col gap-2">
                    <label className="text-xs text-slate-400 font-medium">Costo ElevenLabs (por 1M chars)</label>
                    <input 
                      type="number" step="0.001"
                      className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                      value={costRates.elevenlabs}
                      onChange={(e) => saveCostRates({...costRates, elevenlabs: parseFloat(e.target.value) || 0})}
                    />
                  </div>
                </div>

                <h3 className="font-semibold text-lg text-slate-200 mb-4 border-b border-slate-800 pb-2">Respaldo y Migración de Sistema</h3>
                
                {isRestarting ? (
                  <div className="bg-slate-950 p-12 rounded-xl border border-indigo-500/50 flex flex-col items-center justify-center mb-8 shadow-[0_0_15px_rgba(99,102,241,0.2)]">
                    <Loader2 size={48} className="text-indigo-500 animate-spin mb-4" />
                    <h3 className="text-xl font-bold text-white mb-2">Reiniciando KodaVox...</h3>
                    <p className="text-slate-400 text-sm text-center max-w-md">Se aplicaron cambios críticos (como el archivo .env) que requieren reiniciar el orquestador. Por favor, espera mientras el sistema se reconecta automáticamente.</p>
                  </div>
                ) : (
                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 flex flex-col gap-6 mb-8">
                    <div className="flex items-start gap-3 bg-amber-500/10 border border-amber-500/20 p-4 rounded-lg">
                      <AlertTriangle size={20} className="text-amber-500 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="text-sm font-semibold text-amber-500 mb-1">¡Advertencia de Seguridad!</h4>
                        <p className="text-xs text-amber-200/70">
                          Si seleccionas exportar las <strong>Credenciales (.env)</strong>, el archivo ZIP resultante contendrá tus contraseñas y llaves de API maestras. Nunca compartas este archivo públicamente.
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-col md:flex-row gap-8 justify-between">
                      <div className="flex-1">
                        <h4 className="font-semibold text-slate-300 mb-3">¿Qué deseas incluir en el paquete ZIP?</h4>
                        <div className="flex flex-col gap-3">
                          <label className="flex items-center gap-3 cursor-not-allowed opacity-70">
                            <input type="checkbox" checked disabled className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-indigo-500" />
                            <div>
                              <span className="text-sm text-slate-300 block">Ajustes y Personalidad</span>
                              <span className="text-[10px] text-slate-500">engine_state.json (Obligatorio)</span>
                            </div>
                          </label>
                          <label className="flex items-center gap-3 cursor-pointer group">
                            <input type="checkbox" checked={exportIncludeEnv} onChange={e => setExportIncludeEnv(e.target.checked)} className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-slate-900" />
                            <div>
                              <span className="text-sm text-slate-300 group-hover:text-white transition-colors block">Credenciales y Puertos</span>
                              <span className="text-[10px] text-slate-500">archivo .env (Requiere reinicio al importar)</span>
                            </div>
                          </label>
                          <label className="flex items-center gap-3 cursor-pointer group">
                            <input type="checkbox" checked={exportIncludeCredentials} onChange={e => setExportIncludeCredentials(e.target.checked)} className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-slate-900" />
                            <div>
                              <span className="text-sm text-slate-300 group-hover:text-white transition-colors block">Credenciales Seguras (Recomendado)</span>
                              <span className="text-[10px] text-slate-500">Llaves de APIs introducidas desde el Dashboard</span>
                            </div>
                          </label>
                          <label className="flex items-center gap-3 cursor-pointer group">
                            <input type="checkbox" checked={exportIncludeRag} onChange={e => setExportIncludeRag(e.target.checked)} className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-slate-900" />
                            <div>
                              <span className="text-sm text-slate-300 group-hover:text-white transition-colors block">Base de Conocimiento Vectorial</span>
                              <span className="text-[10px] text-slate-500">chroma_db/ (Puede aumentar el tamaño del ZIP considerablemente)</span>
                            </div>
                          </label>
                        </div>
                      </div>

                      <div className="flex flex-col gap-3 justify-center border-t md:border-t-0 md:border-l border-slate-800 pt-4 md:pt-0 md:pl-8">
                        <button 
                          onClick={handleExportProfile} 
                          className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-6 py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-colors border border-slate-700 w-full md:w-auto"
                        >
                          <DownloadCloud size={18} /> Exportar Paquete (.zip)
                        </button>
                        
                        <div className="relative w-full md:w-auto">
                          <input type="file" accept=".zip" id="import-profile" className="hidden" onChange={handleImportProfile} disabled={isImporting} />
                          <label 
                            htmlFor="import-profile" 
                            className={`w-full ${isImporting ? 'bg-indigo-500/50 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500 cursor-pointer'} text-white px-6 py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-colors shadow-lg shadow-indigo-500/20`}
                          >
                            {isImporting ? <Loader2 size={18} className="animate-spin" /> : <UploadCloud size={18} />}
                            {isImporting ? "Procesando..." : "Importar Paquete (.zip)"}
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <h3 className="font-semibold text-lg text-slate-200 mb-4 border-b border-slate-800 pb-2">Rastreo de Uso Local (Por Día)</h3>
                <div className="bg-slate-950 rounded-xl border border-slate-800 overflow-hidden">
                  <table className="w-full text-left text-sm text-slate-300">
                    <thead className="bg-slate-900 border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Fecha</th>
                        <th className="px-4 py-3 font-semibold text-right">OpenAI (In)</th>
                        <th className="px-4 py-3 font-semibold text-right">OpenAI (Out)</th>
                        <th className="px-4 py-3 font-semibold text-right">Gemini (Total)</th>
                        <th className="px-4 py-3 font-semibold text-right">ElevenLabs (Chars)</th>
                        <th className="px-4 py-3 font-semibold text-right text-emerald-400">Costo Estimado ($)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(usageStats).length === 0 ? (
                        <tr><td colSpan="6" className="text-center py-4 text-slate-500">No hay datos de consumo registrados aún.</td></tr>
                      ) : (
                        Object.entries(usageStats).sort((a,b) => b[0].localeCompare(a[0])).map(([date, stats]) => {
                          const totalTokensOpenAI = (stats.openai_tokens_in || 0) + (stats.openai_tokens_out || 0);
                          const totalTokensGemini = stats.gemini_tokens || 0;
                          const totalCharsEleven = stats.elevenlabs_chars || 0;
                          const cost = (totalTokensOpenAI / 1000000) * costRates.openai + 
                                       (totalTokensGemini / 1000000) * costRates.gemini + 
                                       (totalCharsEleven / 1000000) * costRates.elevenlabs;
                          
                          return (
                            <tr key={date} className="border-b border-slate-800/50 hover:bg-slate-900/50">
                              <td className="px-4 py-3 font-medium text-slate-200">{date}</td>
                              <td className="px-4 py-3 text-right">{stats.openai_tokens_in?.toLocaleString() || 0}</td>
                              <td className="px-4 py-3 text-right">{stats.openai_tokens_out?.toLocaleString() || 0}</td>
                              <td className="px-4 py-3 text-right">{stats.gemini_tokens?.toLocaleString() || 0}</td>
                              <td className="px-4 py-3 text-right">{stats.elevenlabs_chars?.toLocaleString() || 0}</td>
                              <td className="px-4 py-3 text-right font-bold text-emerald-400">${cost.toFixed(4)}</td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>

              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  )
}

export default App

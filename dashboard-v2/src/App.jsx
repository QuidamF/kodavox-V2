import { useState, useEffect } from 'react'
import { io } from 'socket.io-client'
import { 
  Mic, MicOff, MessageSquare, Cpu, Volume2, 
  Database, Upload, Trash, Plus, User, 
  Settings, Activity, Key, CheckSquare, CreditCard 
} from 'lucide-react'

// Nos conectaremos al motor monolítico
const PORT = import.meta.env.VITE_ENGINE_PORT || '5000';
const SOCKET_URL = `http://localhost:${PORT}`;
const API_URL = `http://localhost:${PORT}/api`;

function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [connected, setConnected] = useState(false);
  
  // Telemetry States
  const [vadActive, setVadActive] = useState(false);
  const [micEnergy, setMicEnergy] = useState(0);
  const [sttText, setSttText] = useState("");
  const [llmStream, setLlmStream] = useState("");
  const [llmProvider, setLlmProvider] = useState("");
  const [ttsActive, setTtsActive] = useState(false);

  // RAG States
  const [collections, setCollections] = useState([]);
  const [activeCollection, setActiveCollection] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // Config States
  const [personalityPrompt, setPersonalityPrompt] = useState("");
  const [elevenlabsVoices, setElevenlabsVoices] = useState([]);
  const [activeVoiceId, setActiveVoiceId] = useState("");
  const [newVoiceName, setNewVoiceName] = useState("");
  const [newVoiceId, setNewVoiceId] = useState("");
  const [wakeWord, setWakeWord] = useState("");
  const [wakeTimeout, setWakeTimeout] = useState(10);

  // Diagnostics States
  const [healthStatus, setHealthStatus] = useState(null);
  const [providersStatus, setProvidersStatus] = useState(null);
  const [usageStats, setUsageStats] = useState({});
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [nativeAudioOutput, setNativeAudioOutput] = useState(true);
  const [robotFaceSync, setRobotFaceSync] = useState(false);

  // Pricing (per 1M)
  const [costRates, setCostRates] = useState(() => {
    const saved = localStorage.getItem("kodavox_costs");
    if (saved) return JSON.parse(saved);
    return { openai: 0.15, gemini: 0.0, elevenlabs: 15.0 }; // Default placeholders
  });

  const saveCostRates = (newRates) => {
    setCostRates(newRates);
    localStorage.setItem("kodavox_costs", JSON.stringify(newRates));
  };

  const fetchConfig = async () => {
    try {
      const resP = await fetch(`${API_URL}/config/personality`);
      if (resP.ok) {
        const data = await resP.json();
        setPersonalityPrompt(data.personality_prompt);
      }
      const resV = await fetch(`${API_URL}/config/voices`);
      if (resV.ok) {
        const data = await resV.json();
        setElevenlabsVoices(data.voices);
        setActiveVoiceId(data.active_voice_id);
      }
      const resW = await fetch(`${API_URL}/config/wakeword`);
      if (resW.ok) {
        const data = await resW.json();
        setWakeWord(data.wake_word);
        setWakeTimeout(data.wake_session_timeout);
      }
      const resH = await fetch(`${API_URL}/config/hardware`);
      if (resH.ok) {
        const data = await resH.json();
        setNativeAudioOutput(data.native_audio_output);
        setRobotFaceSync(data.robot_face_sync);
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
        body: JSON.stringify({ word: wakeWord, timeout: wakeTimeout })
      });
      alert("Configuración de Wakeword guardada exitosamente");
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
        body: JSON.stringify({ prompt: personalityPrompt })
      });
      alert("Personalidad guardada exitosamente");
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
        body: JSON.stringify({ voice_id: id })
      });
      fetchConfig();
    } catch (e) {
      console.error(e);
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
    });
    socket.on('disconnect', () => setConnected(false));

    socket.on('telemetry_mic', (data) => setMicEnergy(data.energy));
    socket.on('telemetry_vad', (data) => setVadActive(data.is_speaking));
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
      <header className="bg-slate-900 border-b border-slate-800 p-6 flex items-center justify-between shadow-md">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
            KodaVox V2
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Dashboard & Configuration Center</p>
        </div>
        <div className={`px-4 py-2 rounded-full font-medium flex items-center gap-2 text-sm ${connected ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`}></div>
          {connected ? 'Motor Conectado' : 'Esperando Motor...'}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar Navigation */}
        <aside className="w-64 bg-slate-900/50 border-r border-slate-800 p-4 flex flex-col gap-2 overflow-y-auto">
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
                <Icon size={18} />
                {tab.label}
              </button>
            )
          })}
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-8 text-slate-200">
          
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
                      <span>{micEnergy}</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-3 overflow-hidden">
                      <div 
                        className="bg-blue-500 h-3 transition-all duration-75"
                        style={{ width: `${Math.min(100, (micEnergy / 2000) * 100)}%` }}
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
                
                <form onSubmit={handleSavePersonality} className="flex flex-col flex-1">
                  <textarea
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-xl p-5 text-slate-200 outline-none focus:border-pink-500 focus:ring-1 focus:ring-pink-500/50 mb-6 resize-y transition-all"
                    value={personalityPrompt}
                    onChange={(e) => setPersonalityPrompt(e.target.value)}
                    placeholder="Ej: Eres un asistente virtual sarcástico y muy útil..."
                  />
                  <button type="submit" className="bg-pink-600 hover:bg-pink-500 text-white px-6 py-3 rounded-xl font-medium transition-colors self-end flex items-center gap-2 shadow-lg shadow-pink-500/20">
                    Guardar Personalidad
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
                    <div className="bg-slate-950 border border-slate-800 rounded-xl flex items-center px-4 focus-within:border-amber-500 transition-colors w-1/2">
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

                  <button type="submit" className="bg-amber-600 hover:bg-amber-500 text-white px-6 py-3 rounded-xl font-medium transition-colors self-end mt-4 shadow-lg shadow-amber-500/20">
                    Guardar Configuración
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

                <div className="mb-8 bg-slate-950/50 p-6 rounded-xl border border-slate-800/50 flex items-center justify-between">
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800">
                    <h3 className="font-semibold mb-4 text-slate-300">Añadir Nueva Voz</h3>
                    <form onSubmit={handleAddVoice} className="flex flex-col gap-4">
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
                  </div>

                  <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 flex flex-col">
                    <h3 className="font-semibold mb-4 text-slate-300">Voces Registradas</h3>
                    <div className="space-y-3 flex-1 overflow-y-auto pr-2">
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
                    { label: "Modelo VAD (Silero)", status: healthStatus?.vad },
                    { label: "Modelo STT (Whisper)", status: healthStatus?.stt },
                    { label: "Proveedor LLM", status: healthStatus?.llm },
                    { label: "Conexión RAG (Chroma)", status: healthStatus?.rag },
                    { label: "Micrófono Abierto", status: healthStatus?.microphone_active },
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
                    <span className="font-medium text-slate-300">Estado del Motor</span>
                    <div className="flex gap-2">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${vadActive ? 'bg-orange-500/20 text-orange-400' : 'bg-slate-800 text-slate-500'}`}>
                        {vadActive ? 'Hablando' : 'Silencio'}
                      </span>
                      <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${llmStream || ttsActive ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-800 text-slate-500'}`}>
                        {llmStream || ttsActive ? 'Procesando' : 'Idle'}
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

                <h3 className="font-semibold text-lg text-slate-200 mb-4 border-b border-slate-800 pb-2">Estado de APIs</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                  {/* OpenAI */}
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
                  {/* Gemini */}
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
                  {/* ElevenLabs */}
                  <div className="bg-slate-950 p-5 rounded-xl border border-slate-800 flex flex-col items-center text-center">
                    <h4 className="font-semibold text-slate-300 mb-2">ElevenLabs</h4>
                    {providersStatus?.elevenlabs?.status === 'ok' ? (
                      <div className="flex flex-col items-center">
                        <span className="text-emerald-400 font-medium mb-1">Conectado ({providersStatus.elevenlabs.status_tier})</span>
                        <div className="text-xs text-slate-400">
                          {providersStatus.elevenlabs.character_count?.toLocaleString()} / {providersStatus.elevenlabs.character_limit?.toLocaleString()} chars
                        </div>
                        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2">
                          <div className="bg-emerald-500 h-1.5 rounded-full" style={{width: `${Math.min(100, (providersStatus.elevenlabs.character_count / providersStatus.elevenlabs.character_limit)*100)}%`}}></div>
                        </div>
                      </div>
                    ) : providersStatus?.elevenlabs?.status === 'missing_key' ? (
                      <span className="text-slate-500">No Configurado</span>
                    ) : (
                      <span className="text-red-400 font-medium">Error de Conexión</span>
                    )}
                  </div>
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

import { useState, useEffect } from 'react'
import { io } from 'socket.io-client'
import { Mic, MicOff, MessageSquare, Cpu, Volume2, Database, Upload, Trash, Plus } from 'lucide-react'

// Nos conectaremos al motor monolítico (cuando esté corriendo en el puerto 5000)
const SOCKET_URL = 'http://localhost:5000';
const API_URL = 'http://localhost:5000/api';

function App() {
  const [connected, setConnected] = useState(false);
  const [vadActive, setVadActive] = useState(false);
  const [micEnergy, setMicEnergy] = useState(0);
  const [sttText, setSttText] = useState("");
  const [llmStream, setLlmStream] = useState("");
  const [llmProvider, setLlmProvider] = useState("");
  const [ttsActive, setTtsActive] = useState(false);

  // Estados de RAG
  const [collections, setCollections] = useState([]);
  const [activeCollection, setActiveCollection] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

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

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      reconnectionAttempts: 5,
    });

    socket.on('connect', () => {
      setConnected(true);
      fetchCollections();
    });
    socket.on('disconnect', () => setConnected(false));

    // Eventos de telemetría esperados desde el motor monolítico
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

  return (
    <div className="min-h-screen p-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
            KodaVox V2 Dashboard
          </h1>
          <p className="text-slate-400 mt-1">Diagnostic & Telemetry Center</p>
        </div>
        <div className={`px-4 py-2 rounded-full font-medium flex items-center gap-2 ${connected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`}></div>
          {connected ? 'Motor Conectado' : 'Esperando Motor...'}
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* VAD & Micrófono */}
        <div className="bg-surface p-6 rounded-xl border border-slate-700/50 shadow-lg">
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
        <div className="bg-surface p-6 rounded-xl border border-slate-700/50 shadow-lg lg:col-span-2">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 rounded-lg bg-blue-500/20 text-blue-400">
              <MessageSquare size={24} />
            </div>
            <h2 className="text-xl font-semibold">Transcripción (Whisper STT)</h2>
          </div>
          <div className="bg-slate-900 rounded-lg p-4 min-h-[120px] font-mono text-slate-300 border border-slate-800">
            {sttText || <span className="text-slate-600">Esperando entrada de voz...</span>}
          </div>
        </div>

        {/* LLM */}
        <div className="bg-surface p-6 rounded-xl border border-slate-700/50 shadow-lg lg:col-span-2">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 rounded-lg bg-purple-500/20 text-purple-400">
              <Cpu size={24} />
            </div>
            <h2 className="text-xl font-semibold">
              Respuesta LLM {llmProvider ? `(${llmProvider.toUpperCase()})` : ''}
            </h2>
          </div>
          <div className="bg-slate-900 rounded-lg p-4 min-h-[200px] font-mono text-slate-300 border border-slate-800 whitespace-pre-wrap">
            {llmStream || <span className="text-slate-600">Esperando procesamiento...</span>}
          </div>
        </div>

        {/* TTS */}
        <div className="bg-surface p-6 rounded-xl border border-slate-700/50 shadow-lg">
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

      {/* Panel de Gestión RAG */}
      <div className="mt-8 bg-surface p-6 rounded-xl border border-slate-700/50 shadow-lg">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 rounded-lg bg-teal-500/20 text-teal-400">
            <Database size={24} />
          </div>
          <h2 className="text-xl font-semibold flex-1">Base de Conocimientos (RAG)</h2>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Cerebro Activo:</span>
            <select 
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-200 outline-none focus:border-teal-500"
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

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Subida de Archivos */}
          <div className="bg-slate-800/50 p-5 rounded-lg border border-slate-700">
            <h3 className="font-medium text-slate-300 mb-4 flex items-center gap-2">
              <Upload size={18} /> Subir Documento (.txt, .md, .pdf)
            </h3>
            
            <form onSubmit={handleUpload} className="space-y-4">
              {collections.length === 0 ? (
                <p className="text-sm text-amber-400">Crea una colección primero para subir archivos.</p>
              ) : (
                <>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-slate-400">Colección Destino:</label>
                    <select 
                      className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 outline-none focus:border-teal-500"
                      value={activeCollection || collections[0]}
                      onChange={(e) => setActiveCollection(e.target.value)}
                    >
                      {collections.map(c => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <input 
                    type="file" 
                    accept=".txt,.md,.pdf,.json,.csv"
                    onChange={(e) => setUploadFile(e.target.files[0])}
                    className="block w-full text-sm text-slate-400
                      file:mr-4 file:py-2 file:px-4
                      file:rounded-full file:border-0
                      file:text-sm file:font-semibold
                      file:bg-teal-500/10 file:text-teal-400
                      hover:file:bg-teal-500/20"
                  />
                  <button 
                    type="submit" 
                    disabled={isUploading || !uploadFile}
                    className="bg-teal-600 hover:bg-teal-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {isUploading ? 'Subiendo...' : 'Subir e Indexar'}
                  </button>
                </>
              )}
            </form>
          </div>

          {/* Gestión de Colecciones */}
          <div className="bg-slate-800/50 p-5 rounded-lg border border-slate-700">
            <h3 className="font-medium text-slate-300 mb-4 flex items-center gap-2">
              <Database size={18} /> Administrar Colecciones
            </h3>
            
            <form onSubmit={handleCreateCollection} className="flex gap-2 mb-4">
              <input 
                type="text" 
                placeholder="Nueva colección..." 
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
              />
              <button 
                type="submit"
                className="bg-slate-700 hover:bg-slate-600 px-3 py-2 rounded-lg transition-colors text-white"
              >
                <Plus size={18} />
              </button>
            </form>

            <div className="space-y-2 max-h-40 overflow-y-auto pr-2">
              {collections.map(c => (
                <div key={c} className="flex items-center justify-between bg-slate-900/50 p-3 rounded-lg border border-slate-800/50">
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
                <p className="text-sm text-slate-500 text-center py-2">No hay colecciones creadas.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

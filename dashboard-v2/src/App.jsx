import { useState, useEffect } from 'react'
import { io } from 'socket.io-client'
import { Mic, MicOff, Activity, MessageSquare, Cpu, Volume2 } from 'lucide-react'

// Nos conectaremos al motor monolítico (cuando esté corriendo en el puerto 5000)
const SOCKET_URL = 'http://localhost:5000';

function App() {
  const [connected, setConnected] = useState(false);
  const [vadActive, setVadActive] = useState(false);
  const [micEnergy, setMicEnergy] = useState(0);
  const [sttText, setSttText] = useState("");
  const [llmStream, setLlmStream] = useState("");
  const [llmProvider, setLlmProvider] = useState("");
  const [ttsActive, setTtsActive] = useState(false);

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      reconnectionAttempts: 5,
    });

    socket.on('connect', () => setConnected(true));
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
    </div>
  )
}

export default App

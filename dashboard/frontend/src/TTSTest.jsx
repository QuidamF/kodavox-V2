import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Volume2, Play, Square, Settings, Activity } from 'lucide-react';

const TTS_API_BASE = "http://localhost:8001/api/tts"; // API Directa TTS

export default function TTSTest() {
    const [text, setText] = useState("Hola, esta es una prueba de generación de voz aislada.");
    const [loading, setLoading] = useState(false);
    const [logs, setLogs] = useState([]);
    const [audioUrl, setAudioUrl] = useState(null);

    const audioContextRef = useRef(null);
    const nextStartTimeRef = useRef(0);
    const activeSourcesRef = useRef([]);
    const abortControllerRef = useRef(null);

    const addLog = (msg) => {
        const time = new Date().toLocaleTimeString();
        setLogs(prev => [{ time, msg }, ...prev]);
    };

    const handleBatchTest = async () => {
        setLoading(true);
        setAudioUrl(null);
        addLog("Iniciando prueba BATCH...");
        try {
            const response = await axios.post(`${TTS_API_BASE}/batch`,
                { text },
                { responseType: 'blob' }
            );

            const url = URL.createObjectURL(response.data);
            setAudioUrl(url);
            addLog("Generación BATCH exitosa. Reproduciendo...");

            // Auto-reproducir
            const audio = new Audio(url);
            audio.play();

        } catch (error) {
            console.error(error);
            addLog(`Error BATCH: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleStreamTest = async () => {
        setLoading(true);
        addLog("Iniciando prueba STREAMING...");

        abortControllerRef.current = new AbortController();

        if (!audioContextRef.current) {
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        }

        if (audioContextRef.current.state === 'suspended') {
            await audioContextRef.current.resume();
        }

        nextStartTimeRef.current = audioContextRef.current.currentTime;

        try {
            const response = await fetch(`${TTS_API_BASE}/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
                signal: abortControllerRef.current.signal
            });

            if (!response.body) throw new Error("ReadableStream no soportado");

            const reader = response.body.getReader();
            addLog("Conectado al stream. Esperando chunks...");

            let chunkCount = 0;

            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    addLog(`Stream completado. Total chunks: ${chunkCount}`);
                    break;
                }

                chunkCount++;
                addLog(`Recibido chunk #${chunkCount} (${value.length} bytes)`);

                // El TTS envía raw Int16 PCM a 24000Hz
                const int16View = new Int16Array(value.buffer, value.byteOffset, value.length / 2);
                const float32Buffer = audioContextRef.current.createBuffer(1, int16View.length, 24000);
                const channelData = float32Buffer.getChannelData(0);

                for (let i = 0; i < int16View.length; i++) {
                    channelData[i] = int16View[i] / 32768.0;
                }

                const source = audioContextRef.current.createBufferSource();
                source.buffer = float32Buffer;
                source.connect(audioContextRef.current.destination);

                const currentTime = audioContextRef.current.currentTime;
                if (nextStartTimeRef.current < currentTime) {
                    nextStartTimeRef.current = currentTime;
                }

                const startAt = nextStartTimeRef.current;
                source.start(startAt);
                activeSourcesRef.current.push(source);

                source.onended = () => {
                    activeSourcesRef.current = activeSourcesRef.current.filter(s => s !== source);
                };

                nextStartTimeRef.current = startAt + float32Buffer.duration;
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                addLog("Stream interrumpido por el usuario.");
            } else {
                console.error(error);
                addLog(`Error STREAM: ${error.message}`);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleStopStream = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        activeSourcesRef.current.forEach(source => {
            try { source.stop(); source.disconnect(); } catch (e) { }
        });
        activeSourcesRef.current = [];
        addLog("Reproducción detenida manualmente.");
    };

    return (
        <div className="space-y-6">
            <div className="glass-card">
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                    <Volume2 className="text-orange-500" /> Entorno Aislado de Pruebas TTS
                </h2>
                <p className="text-sm text-gray-600 mb-6">
                    Esta vista se conecta directamente al servicio TTS (en el puerto 8004) evadiendo el Orquestador y Socket.IO para validar la generación de audio cruda.
                </p>

                <div className="mb-4">
                    <label className="block text-sm font-semibold mb-2">Texto a sintetizar</label>
                    <textarea
                        className="w-full p-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-orange-500 bg-white/80"
                        rows={4}
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                    />
                </div>

                <div className="flex gap-4 mb-8">
                    <button
                        onClick={handleBatchTest}
                        disabled={loading}
                        className="flex-1 py-3 px-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-bold transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        <Activity size={18} /> Validar Modo Batch
                    </button>

                    <button
                        onClick={handleStreamTest}
                        disabled={loading}
                        className="flex-1 py-3 px-4 bg-orange-600 hover:bg-orange-700 text-white rounded-xl font-bold transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        <Play size={18} /> Validar Modo Streaming
                    </button>

                    <button
                        onClick={handleStopStream}
                        className="py-3 px-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold transition-all flex items-center justify-center gap-2"
                    >
                        <Square size={18} /> Detener
                    </button>
                </div>

                {audioUrl && (
                    <div className="mb-6 p-4 bg-gray-100 rounded-xl">
                        <p className="text-sm font-semibold mb-2">Audio Batch Generado:</p>
                        <audio src={audioUrl} controls className="w-full" />
                    </div>
                )}

                <div>
                    <h3 className="text-sm font-semibold mb-2">Log de Depuración:</h3>
                    <div className="bg-black/80 rounded-xl p-4 font-mono text-xs overflow-y-auto h-[200px] border border-gray-700 text-green-400 select-all">
                        {logs.map((log, i) => (
                            <div key={i} className="mb-1">
                                <span className="text-gray-500 mr-2">[{log.time}]</span>
                                <span>{log.msg}</span>
                            </div>
                        ))}
                        {logs.length === 0 && <span className="text-gray-600">No hay registros aún...</span>}
                    </div>
                </div>

            </div>
        </div>
    );
}

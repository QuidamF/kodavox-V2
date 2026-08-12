[← Volver al Índice Principal](../README.md)

# 📊 Interfaz de Usuario y Configuración (Dashboard V2)

Una vez iniciado el sistema, abre tu navegador en:
👉 **http://localhost:5173** (o el puerto consecutivo si está ocupado)

El Dashboard consta de un menú lateral que te permite monitorizar el estado en tiempo real y configurar el comportamiento del agente "al vuelo", sin necesidad de reiniciar el servidor. Aquí tienes una guía de uso para cada sección:

### 1. Monitoreo (Home)
Esta es la pantalla principal para observar qué está "pensando" el motor.
- **Voice Activity (VAD)**: Muestra una barra de energía en tiempo real. Si el indicador cambia a verde ("Usuario Hablando..."), el sistema te está escuchando.
- **Transcripción (STT)**: Lee exactamente lo que el modelo Whisper entendió de tu voz. Útil para verificar si la sensibilidad del micrófono o el ruido de fondo están afectando el reconocimiento.
- **Respuesta LLM**: El flujo de texto palabra por palabra generado por Ollama, OpenAI o Gemini.
- **Síntesis (TTS)**: Indica si el agente está hablando o en silencio.

### 2. Personalidad
Define cómo razona y responde KodaVox mediante un **System Prompt**.
- **Ejemplo de llenado:** `"Eres KodaVox, un asistente técnico muy inteligente pero sarcástico. Siempre respondes en menos de 2 oraciones."`
- *Nota:* Al presionar "Guardar Personalidad", el nuevo comportamiento se aplicará instantáneamente en tu siguiente interacción verbal.

### 3. Wakeword (Palabra Mágica)
Si el `INTERACTION_MODE` en tu `.env` está configurado como `wakeword`, aquí defines cómo despertar al asistente.
- **Palabra de Activación**: El nombre al cual responde. Ejemplo: `Computadora` o `Jarvis`.
- **Temporizador de Sesión**: Los segundos que permanecerá atento a comandos subsecuentes sin necesidad de repetir su nombre (Ej. `10` segundos).

### 4. Voz (Catálogo y Clonación ElevenLabs)
Si usas `TTS_PROVIDER=elevenlabs`, aquí puedes registrar nuevas voces, personalizar su estilo y alternar entre ellas de forma dinámica.

- **Seleccionar Voz**: Usa el menú desplegable superior para cambiar la voz activa al instante.
- **Personalización de Emoción y Estilo**:
  - **Estabilidad**: Define qué tan variable y emotiva (0.0) o qué tan fija y monótona (1.0) suena la voz.
  - **Similitud**: Qué tan apegada es la lectura a la voz clonada original.
  - **Exageración de Estilo**: Amplifica el estilo y las emociones deducidas del texto.
- **Añadir Nueva Voz (Por ID)**: Coloca un "Nombre Descriptivo" (Ej. `Drew (Narrador)`) y pega el "ID de ElevenLabs" (una cadena alfanumérica).
- **Añadir Nueva Voz (Clonar)**: Crea voces en vivo subiendo un archivo `.mp3` / `.wav` o grabando directamente con tu micrófono desde el navegador.

> [!WARNING]
> **Limitación de Clonación:** La creación de nuevas voces (Clonación) requiere de una suscripción de pago en ElevenLabs (Plan *Starter* o superior). Si estás en el plan **gratuito (Free Tier)**, recibirás un error `401 Unauthorized` al intentar clonar. Si es tu caso, usa la pestaña "Por ID" para agregar las voces pre-hechas listadas abajo.

**Voces Populares de ElevenLabs (Ejemplos para añadir "Por ID"):**
- **Rachel** (Femenina, Americana, Narración): `21m00Tcm4TlvDq8ikWAM` *(Voz por defecto)*
- **Drew** (Masculino, Americano, Noticias): `29vD33N1CtxCmqQRPOHJ`
- **Antoni** (Masculino, Americano, Calmado): `ErXwobaYiN019PkySvjV`
- **Domi** (Femenina, Americana, Emocional): `AZnzlk1XvdvUeBnXmlld`
- **Elli** (Femenina, Americana, Infantil/Emocional): `MF3mGyEYCl7XYWbV9V6O`
- **Fin** (Masculino, Irlandés, Profundo): `D38z5RcWu1voky8WS1ja`

### 5. Base de Conocimientos (RAG)
Permite inyectar información contextual a largo plazo para que el LLM responda con datos específicos de tu organización.
- **Paso 1 (Crear Colección)**: En el panel izquierdo, escribe un nombre (ej. `manual_empleados`) y da clic en "Crear".
- **Paso 2 (Subir Documento)**: En el panel derecho, asegúrate de que la colección de destino esté seleccionada, elige un archivo de tu computadora (soportados: `.txt, .md, .pdf, .json, .csv`) y presiona "Subir e Indexar Documento".
- **Paso 3 (Activar)**: En la esquina superior derecha, bajo la caja "Cerebro Activo", selecciona la colección que quieres que el agente lea.
- *Ejemplo de interacción:* Sube un PDF del manual de tu empresa y luego pregúntale a KodaVox por el micrófono: *"¿Cuáles son las políticas de vacaciones según el manual?"*.

### 6. Diagnósticos y Proveedores
- **Diagnósticos**: Muestra semáforos (OK/Falla) para los módulos internos de hardware (VAD, Whisper, Base de Datos). Aquí también puedes usar los *Toggles* (interruptores) para apagar la salida física de audio, o bien, encender la **Sincronización de Estados con Robot Face**.
- **Proveedores**: Define tus costos por "Millón de tokens/caracteres" para monitorear cuánto dinero real has consumido en el día usando las APIs en la nube.

---

## 💾 Respaldo y Migración (Exportación ZIP)
En la sección de Diagnósticos puedes empaquetar toda la "mente" de KodaVox en un solo archivo `.zip` para clonar el agente en otra computadora o robot.

1. **Elige qué exportar**:
   - `Ajustes y Personalidad` (Siempre incluido)
   - `Credenciales (.env)`: Exporta tus contraseñas y llaves de API. (Opcional)
   - `Base de Conocimiento (RAG)`: Exporta la carpeta `chroma_db` entera. (Opcional)
2. **Importación y Reinicio Automático**: Al importar un perfil ZIP en otro robot, si dicho paquete contiene un archivo `.env`, el dashboard te avisará y el sistema se reiniciará automáticamente para aplicar las nuevas llaves maestras sin necesidad de tocar la terminal.

## 💰 Sistema de Costos
El motor guarda diariamente los consumos en `orchestrator/data/usage_stats.json`. En la pestaña de **Proveedores** del Dashboard puedes configurar cuánto pagas por Millón de tokens/caracteres, y KodaVox calculará tu gasto del día en tiempo real.

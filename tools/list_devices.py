import pyaudio
import sys

def list_devices():
    p = pyaudio.PyAudio()
    print("\n--- PyAudio Devices (Orchestrator Env) ---")
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            name = p.get_device_info_by_host_api_device_index(0, i).get('name')
            print(f"Device {i}: {name}")
    print("------------------------------------------\n")
    p.terminate()

if __name__ == "__main__":
    try:
        list_devices()
    except Exception as e:
        print(f"Error: {e}")

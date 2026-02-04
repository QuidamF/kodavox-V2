import pyaudio

def list_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    
    print("--- Audio Devices ---")
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
            dev = p.get_device_info_by_host_api_device_index(0, i)
            print(f"Index {i}: {dev.get('name')}")

    p.terminate()

if __name__ == "__main__":
    list_devices()

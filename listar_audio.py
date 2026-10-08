import pyaudio

p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    d = p.get_device_info_by_index(i)
    print(
        f"{i:>3} | entradas: {d['maxInputChannels']} | salidas: {d['maxOutputChannels']} | {d['name']}"
    )

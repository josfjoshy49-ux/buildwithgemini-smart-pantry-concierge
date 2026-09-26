import wave
import math
import struct
import random

def create_lofi_track(filename="lofi_track.wav", duration_sec=45, sample_rate=44100):
    bpm = 85
    beat_dur = 60.0 / bpm  # ~0.7058 sec
    measure_dur = beat_dur * 4  # ~2.823 sec
    num_samples = int(sample_rate * duration_sec)
    
    # Jazz / Lo-Fi Chords (Frequencies in Hz)
    # 1: Cmaj7, 2: Am9, 3: Dm7, 4: G13
    chords = [
        [261.63, 329.63, 392.00, 493.88, 659.25],  # Cmaj7 (C4, E4, G4, B4, E5)
        [220.00, 261.63, 329.63, 392.00, 493.88],  # Am9 (A3, C4, E4, G4, B4)
        [293.66, 349.23, 440.00, 523.25, 698.46],  # Dm9 (D4, F4, A4, C5, F5)
        [196.00, 246.94, 293.66, 349.23, 523.25]   # G7/13 (G3, B3, D4, F4, C5)
    ]

    samples = [0.0] * num_samples
    
    # Generate Lo-Fi Rhodie / Electric Piano Chord Accompaniment
    for t_idx in range(num_samples):
        t = t_idx / sample_rate
        measure_num = int(t / measure_dur)
        chord = chords[measure_num % len(chords)]
        t_in_measure = t % measure_dur
        
        # Strum chord at start of measure and on beat 3
        note_trigger = t_in_measure if t_in_measure < beat_dur * 2 else t_in_measure - beat_dur * 2
        env = math.exp(-2.2 * note_trigger)  # Smooth piano key decay
        
        piano_val = 0.0
        for i, freq in enumerate(chord):
            # Soft harmonics for warm electric piano / vibraphone tone
            harm1 = math.sin(2 * math.pi * freq * t)
            harm2 = 0.35 * math.sin(2 * math.pi * freq * 2 * t)
            harm3 = 0.15 * math.sin(2 * math.pi * freq * 3 * t)
            piano_val += (harm1 + harm2 + harm3) * (0.8 ** i)
            
        samples[t_idx] += piano_val * env * 0.18

    # Generate Upbeat Lo-Fi Drum Beat (Kick, Snare, Hi-Hat)
    for t_idx in range(num_samples):
        t = t_idx / sample_rate
        beat_pos = (t % measure_dur) / beat_dur  # 0.0 to 4.0 within measure
        
        # Kick drum on 1.0 and 2.75
        kick_env = 0.0
        pos_in_beat1 = beat_pos
        pos_in_beat2_75 = beat_pos - 2.5
        if 0 <= pos_in_beat1 < 0.2:
            kick_env = math.exp(-25 * pos_in_beat1) * math.sin(2 * math.pi * (100 * math.exp(-30 * pos_in_beat1)) * t)
        elif 0 <= pos_in_beat2_75 < 0.2:
            kick_env = math.exp(-25 * pos_in_beat2_75) * math.sin(2 * math.pi * (100 * math.exp(-30 * pos_in_beat2_75)) * t)

        # Snare/Rimshot on beat 2.0 and 4.0
        snare_env = 0.0
        s1 = beat_pos - 1.0
        s2 = beat_pos - 3.0
        if 0 <= s1 < 0.15:
            noise = (random.random() * 2 - 1)
            snare_env = math.exp(-30 * s1) * (noise * 0.7 + 0.3 * math.sin(2 * math.pi * 180 * t))
        elif 0 <= s2 < 0.15:
            noise = (random.random() * 2 - 1)
            snare_env = math.exp(-30 * s2) * (noise * 0.7 + 0.3 * math.sin(2 * math.pi * 180 * t))

        # Hi-hat on eighth notes
        hat_env = 0.0
        hat_sub = (beat_pos * 2) % 1.0
        if hat_sub < 0.08:
            hat_env = math.exp(-60 * hat_sub) * (random.random() * 2 - 1) * 0.12

        # Soft vinyl noise warmth
        vinyl = (random.random() * 2 - 1) * 0.008

        samples[t_idx] += (kick_env * 0.35 + snare_env * 0.22 + hat_env + vinyl)

    # Normalize & convert to 16-bit PCM WAV
    max_amp = max(abs(s) for s in samples) or 1.0
    scale = 28000 / max_amp

    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        packed_frames = bytearray()
        for s in samples:
            sample_val = int(max(-32768, min(32767, s * scale)))
            packed_frames.extend(struct.pack('<h', sample_val))
            
        wav_file.writeframes(packed_frames)

    print(f"Upbeat lo-fi track generated: {filename}")

if __name__ == "__main__":
    create_lofi_track()

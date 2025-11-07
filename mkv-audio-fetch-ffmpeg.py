import argparse
import os
import sys
from pymkv import MKVFile, MKVTrack
import ffmpeg
import iso639

# Extract audio tracks from video file using ffmpeg if the pymkv fails
def extract_audio_ffmpeg(video_file, language, output_ext="aac", default_bitrate=196000, max_bitrate=320000):
    filename, ext = os.path.splitext(video_file)
    audio_tracks = get_audio_tracks_info(video_file)
    if not audio_tracks:
        print("No audio tracks found in input file.")
        return []
    print(f"Found {len(audio_tracks)} audio track(s) in input file:")
    tracks_lang_map = {track['idx']: track['language'] for track in audio_tracks}
    for idx, lang_code in tracks_lang_map.items():
        print(f"    Track {idx}: Language = {lang_code}")
    
    selected_tracks = select_audio_tracks_to_extract(audio_tracks, language)
    if not selected_tracks:
        print(f"No audio suitable tracks found for language '{language.name}'. Exiting.")
        return []
    print(f"Selected {len(selected_tracks)} track(s) for extraction:")
    for track in selected_tracks:
        print(f"    Track {track['idx']}: Language = {track['language']}, Codec = {track['codec_name']}, Channels = {track['channels']}, Sample Rate = {track['sample_rate']}Hz, Bitrate = {track['bit_rate']} bit/s")
    print("Starting conversion...")
    for track in selected_tracks:
        if len(selected_tracks) > 1:
            track["output_file"] = f"{filename}_track{track['idx']}.{output_ext}"
        else:
            track["output_file"] = f"{filename}.{output_ext}"
        print(f"    Track {track['idx']}")
        if track['bit_rate'] == 'N/A':
            print(f"        Extracting to audio with default bitrate: {default_bitrate} bits/s")
            audio_bitrate = default_bitrate
        elif int(track['bit_rate']) > max_bitrate:
            print(f"        Input audio bitrate {track['bit_rate']} bits/s is higher than max bitrate ({max_bitrate} bits/s). Using max bitrate: {max_bitrate} bits/s")
            audio_bitrate = max_bitrate  
        else:
            print(f"        Extracting to audio with same audio bitrate as input: {track['bit_rate']} bits/s")
            audio_bitrate = int(track['bit_rate'])  
        ffmpeg.input(video_file).output(track["output_file"], audio_bitrate=f"{audio_bitrate}").run(overwrite_output=True)

    print("Extraction completed.")
    print("Extracted files:")
    for track in selected_tracks:
        print(f"    {track['output_file']}")
    
    return selected_tracks

# Select audio tracks to extract based on preferred language for ffmpeg extraction
def select_audio_tracks_to_extract(audio_tracks, language):
    selected_tracks = []
    for track in audio_tracks:
        track_lang_iso = iso639.Language.match(track['language'])
        if track_lang_iso == language:
            selected_tracks.append(track)
    
    if not selected_tracks:
        print(f"No audio tracks found for language '{language.name}'. Assuming tag is missing and exporting the one(s) with N/A.")
        for track in audio_tracks:
            if track['language'] == "und":
                selected_tracks.append(track)
    return selected_tracks

# Get audio tracks information from input file using ffmpeg probe
def get_audio_tracks_info(input_file):
    try:
        probe = ffmpeg.probe(input_file)
        audio_tracks = [s for s in probe['streams'] if s['codec_type'] == 'audio']
        audio_tracks_info = []
        for idx, track in enumerate(audio_tracks):
            info = {
                "idx": idx,
                "codec_name": track.get('codec_name', 'N/A'),
                "channels": track.get('channels', 'N/A'),
                "sample_rate": track.get('sample_rate', 'N/A'),
                "bit_rate": track.get('bit_rate', 'N/A'),
                "language": track['tags']['language'] if 'tags' in track and 'language' in track['tags'] else 'und'
            }
            audio_tracks_info.append(info)
        return audio_tracks_info

    except ffmpeg.Error as e:
        print("FFmpeg error occurred.")
        print(e.stderr.decode() if e.stderr else str(e))
        return []

# Extract audio tracks from MKV file using pymkv, fallback to ffmpeg if fails
def extract_audio(mkv_file, language):
    selected_tracks = []
    try:
        mkv = MKVFile(mkv_file)
        mkv_tracks = mkv.get_track()
        audio_tracks = []
        for track in mkv_tracks:
            if track.track_type == "audio":
                audio_tracks.append(track)
        for track in audio_tracks:
            if track.language:
                if iso639.Language.match(track.language) == language:
                    selected_tracks.append(track)
        if not selected_tracks:
            print(f"No audio tracks found for language '{language.name}'. Assuming tag is missing and exporting the one(s) with 'und' language.")
            for track in audio_tracks:
                if track.language == "und" or not track.language:
                    # Overwritting language to desired one
                    track.language = language.part2b
                    selected_tracks.append(track)
        return selected_tracks
    
    except Exception as e:
        print(f"Error extracting audio from MKV file: {e}")
        print(f"Extracting audio using ffmpeg instead.")
        audio_tracks_ffmpeg = extract_audio_ffmpeg(audio_file, lang_iso)
        for audio_file in audio_tracks_ffmpeg:
            audio_track = MKVTrack(audio_file["output_file"], language=audio_file['language'], default_track=False)
            selected_tracks.append(audio_track)
        return selected_tracks

# Extract subtitle tracks from MKV file using pymkv
def extract_subs(mkv_file, language):
    selected_tracks = []
    try:
        mkv = MKVFile(mkv_file)
        mkv_tracks = mkv.get_track()
        sub_tracks = []
        for track in mkv_tracks:
            if track.track_type == "subtitles":
                sub_tracks.append(track)
        for track in sub_tracks:
            if track.language:
                if iso639.Language.match(track.language) == language:
                    selected_tracks.append(track)
        
        return selected_tracks
    
    except Exception as e:
        print(f"Error extracting subtitles from MKV file: {e}")
        print(f"No subtitles extracted.")
        return []

# Mux extracted audio tracks and sub tracks into video file
def mux_tracks_with_video(video_file, audio_tracks, sub_tracks, language, output_file):
    if not audio_tracks:
        print("No audio tracks to mux. Exiting.")
        return
    mkv_video = MKVFile(video_file)
    mkv_video_tracks = mkv_video.get_track()
    # Set all existing audio and subtitles tracks to non-default
    found_forced_sub = False
    for track in mkv_video_tracks:
        if track.track_type == "audio":
            track.default_track = False
            #mkv_video.replace_track(track.track_id, track)
        if track.track_type == "subtitles":
            if iso639.Language.match(track.language) == language and track.forced_track:
                track.default_track = True
                found_forced_sub = True
            else:
                track.default_track = False
            #mkv_video.replace_track(track.track_id, track)
    # Add new audio tracks
    for idx, track in enumerate(audio_tracks):
        track.default_track = idx == 0  # Set the first added track as default
        mkv_video.add_track(track)
    
    # Add subtitle tracks
    for track in sub_tracks:
        if track.forced_track and not found_forced_sub:
            track.default_track = True
        else:
            track.default_track = False
        mkv_video.add_track(track)
    try:
        mkv_video.mux(output_file)
        print(f"Muxing completed. Output file: {output_file}")
    except Exception as e:
        print(f"Error muxing tracks into MKV file: {e}")
        print("Output might be corrupted or incomplete.")

def check_language_in_video(mkv_file, language):
    try:
        mkv = MKVFile(mkv_file)
        mkv_tracks = mkv.get_track()
        for track in mkv_tracks:
            if track.track_type == "audio" and track.language:
                if iso639.Language.match(track.language) == language:
                    return True
        return False
    
    except Exception as e:
        print(f"Error checking language in MKV file: {e}")
        return False

if __name__ == "__main__":
    # Argument parsing definition
    parser = argparse.ArgumentParser(prog="mkv_audio_fetch", description="Add audio track that matches preferred language from one video file to another.")
    parser.add_argument("-iv", "--input-video", required=True, help="Input video file to which audio track will be added.")
    parser.add_argument("-ia", "--input-audio", required=True, help="Input video/audio file from which audio track will be extracted.")
    parser.add_argument("-l", "--language", required=True, help="Preferred language for audio track (ISO 639-2 code or language name).")
    parser.add_argument("-f", "--force", action="store_true", help="Force addition of audio track even if language is already present in video file.")
    args = parser.parse_args()

    # Properties from arguments
    video_file = args.input_video
    audio_file = args.input_audio
    lang = args.language
    force = args.force

    # Getting the iso639 language code from user input
    lang_iso = iso639.Language.match(lang)
    if not lang_iso:
        print(f"Language '{lang}' not recognized. Exiting.")
        sys.exit(1)

    # Check first if language is already present in video file
    if check_language_in_video(video_file, lang_iso):
        if not force:
            print(f"Language '{lang_iso.name}' is already present in video file. Exiting.")
            sys.exit(0)
        else:
            print(f"Language '{lang_iso.name}' is already present in video file. Forcing addition of new track.")
    
    # Extract audio from file that contains preferred language audio track
    audio_tracks = extract_audio(audio_file, lang_iso)

    # Extract subtitles from file that might contains preferred language subtitles track as well
    sub_tracks = extract_subs(audio_file, lang_iso)

    # Mux extracted audio into video file
    filename, ext = os.path.splitext(video_file)
    output_file = f"{filename}-out.{ext.lstrip('.')}"
    mux_tracks_with_video(video_file, audio_tracks, sub_tracks, lang_iso, output_file)
    
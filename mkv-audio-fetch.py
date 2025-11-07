import argparse
import os
import sys
from pymkv import MKVFile
import iso639

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
    
# mkv-audio-fetch
Tool based on pymkv to automate fetching of audio track in a preferred language and merging in another media file.

## Possible improvements
- adjust audio levels (in progress)
  - add option for audio level adjustment
  - clean exported audio files for audio level adjustment
- check for duration before merging
- clean up file
  - removing other audio/subs tracks (possibility to keep a set of defined languages)
  - set audio tracks language if undefined (if only one in file and native language is provided)
- add option to only export/extract audio tracks in a Jellyfin compatible format 

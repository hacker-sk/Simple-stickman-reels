Background music for the Hindi videos (mp3, wav, m4a or ogg).

Name each song <mood>_<number>.mp3, with mood = motivational, emotional or neutral
(for example motivational_01.mp3, emotional_03.mp3, neutral_02.mp3).
A video's mood (the "mood" field of the payload / chat package) picks one random song from that mood plus the neutral songs.
A neutral video picks from the neutral songs only.
Files without one of these prefixes are not used once any mood-named song exists.

The songs come from the Google Drive folder "Bgm library for hindi reels". To add or change songs: edit
music_hindi/music_manifest.json (name, Drive file id, size) and push it; the "Sync BGM from Drive" workflow copies them here.
The picker code is music_picker.py, started through run_hindi.py.

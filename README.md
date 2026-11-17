# pro-video-editor

A Claude skill that edits raw footage into finished videos for Shorts, TikTok, Reels, YouTube, podcasts and ads. It plans the story from the transcript (Amharic included), cuts with a reason for every cut, mixes, grades, adds captions and motion graphics (HyperFrames, including 3D explainer stages), checks itself with QC, and delivers the video, an editable timeline (Resolve, Premiere, Final Cut), captions, titles and thumbnails. It can also build before/after showcase reels.

Start with [SKILL.md](SKILL.md). Design decisions are logged in [DECISIONS.md](DECISIONS.md).

Setup: `pip install -r requirements.txt` (Amharic transcription: `requirements-amharic.txt`), plus ffmpeg and Node.js for HyperFrames. No third-party fonts, music, footage or icons ship with this repo; scripts fetch licensed assets at run time and record their licences per project.

# Log footage

Read when the footage was shot in a camera log profile, or ingest flags `log_suspected` / `log_approximate`.

## What log is
Log profiles record a flat, grey picture on purpose: stops of light are spread evenly through the code values, so highlights and shadows survive. Black sits high (S-Log3 at 10-bit code 95, V-Log at 128) and 18 % grey sits near 41 % (S-Log3 code 420). Grading it as if it were badly exposed Rec.709 is the classic mistake: the normal correction would "fix" the flatness and wreck skin and contrast.

## The order (what colourists do, node by node)
1. **Colour space transform first** (ingest, `lib/logcam.py`): decode the log curve to scene light, move the camera gamut to Rec.709 primaries, then a display rendering: a tonescale through 18 % grey -> 41 % code with a soft highlight roll-off, out-of-gamut colours pulled toward their own luminance, the brightest colours eased to white.
2. **Balance**: exposure and white balance on the face (`color.correction`, craft-color.md section 1).
3. **Match** shots in a scene.
4. **Look**: the per-video grade (`color.look`, a dict with `hues` bands and `skin_protect`), at a strength.
5. **Finish**: halation, grain, textures.

## Detection (automatic at ingest; `scripts/detect_log.py` for one clip)
1. `--log PROFILE` or `--log none` when the person says so.
2. The camera's metadata: Sony's XML (`CaptureGammaEquation`, `CaptureColorPrimaries`) or a maker marker (V-Log, C-Log3, F-Log2, N-Log, Apple Log, D-Log...). A Sony file saying `rec709`, `hlg` or `s-cinetone` is not log.
3. Maker in the tags plus a flat picture (lifted blacks, no real whites, low saturation) -> that maker's log. Apple counts only when the file is tagged BT.2020 (iPhone SDR is BT.709).
4. Flat picture, unknown maker -> flag `log_suspected`; ask which camera, then ingest again with `--log`.
HLG/PQ HDR is not log: ingest tone-maps it separately.

## Profiles
Formula and gamut from the maker's published papers (via colour-science): `slog3` (S-Gamut3.Cine, the default for S-Log3), `slog3_sg3`, `slog2`, `vlog`, `clog3`, `clog2`, `clog`, `flog`, `flog2`, `nlog`, `llog`, `logc3`, `logc4`, `dlog`, `applelog`, `protune`.
No published formula: `dlogm` (DJI D-Log M), `samsunglog`, `gplog` (GoPro), `ilog` (Insta360). Ask the person for the maker's free log-to-Rec.709 LUT and pass it with `--log-lut`; without it ingest converts approximately from the clip's own levels and flags `log_approximate`.

## Checks
- The conformed clip's face should land in the normal exposure band; qc.py `face_exposure` and `skin_hue` apply as usual.
- Compare one frame before and after (`detect_log.py --cube-dir` writes the conversion .cube for any editor).
- Not yet verified on real camera files: the marker strings other than Sony's XML, and the Apple Log signal range. Confirm on the first real clip of each maker and record it in DECISIONS.md.

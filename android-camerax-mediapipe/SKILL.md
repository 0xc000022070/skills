---
name: android-camerax-mediapipe
description: Run MediaPipe Tasks (pose, hand, face landmarkers) live on Android with CameraX and Jetpack Compose, and draw a stable landmark overlay that lines up with the viewfinder. Use when wiring ImageAnalysis to a landmarker in LIVE_STREAM mode, frames are dropped or the landmarker throws on timestamps, the skeleton is offset, stretched or mirrored wrong relative to the preview, joints flicker or jitter, the app crashes on rotation with the GPU delegate, off-screen limbs are drawn, portrait vs landscape frame sizes confuse downstream geometry, or a Compose camera screen leaves empty space or pushes the preview off screen.
allowed-tools: Read Grep Glob Edit Write
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: mobile
---

# CameraX + MediaPipe live landmarks

```
CameraX Preview ---------------------------> CameraXViewfinder (Crop, mirrored for front)
CameraX ImageAnalysis (RGBA, keep-latest) -> throttle + busy gate -> rotate upright
    -> landmarker.detectAsync(ts strictly increasing) -> result listener
    -> state flow (raw points)  -> consumers that need exact values (counters, uploads)
                                 \-> display smoother -> Canvas overlay (same crop math)
```

Two consumers, two copies. Logic reads the **raw** landmarks. Only the overlay
smooths. See [overlay.md](references/overlay.md).

## Route the work

| Task | Read |
|---|---|
| Analyzer, throttling, timestamps, rotation, delegates, lifecycle | [pipeline.md](references/pipeline.md) |
| Overlay alignment, mirroring, smoothing, visibility, Compose layout | [overlay.md](references/overlay.md) |

## Hard rules

- **Timestamps passed to `detectAsync` must strictly increase**, or the
  landmarker errors and stops producing results. Use
  `ts = max(now, lastTs + 1)`.
- **Gate submissions with an `AtomicBoolean busy`** that the result *and*
  error listeners clear. Otherwise frames pile up inside MediaPipe, and
  latency grows without bound on slow phones.
- **Rotate analysis frames upright yourself** (`imageInfo.rotationDegrees`).
  Downstream geometry assumes y points toward the floor. In portrait the frame
  becomes 480x640 instead of 640x480; carry the real width and height with
  every result.
- **Mirroring belongs to the preview only.** CameraX mirrors the front-camera
  preview but never the analysis frames. Flip x in the overlay only when the
  front lens is active.
- **The overlay must use the viewfinder's crop math.** The preview fills and
  crops (`ContentScale.Crop`), but landmarks are normalized to the uncropped
  analysis frame. Apply the same `scale = max(W/fw, H/fh)` and center offset,
  or the skeleton drifts at the edges.
- **Try the GPU delegate, fall back to CPU**, and log which one you got. Some
  devices and emulators refuse the GPU delegate at creation.
- **Lock orientation while the camera screen is shown.** Rotating mid-inference
  tears down the GPU delegate and crashes. Restore the previous orientation on
  dispose.
- **Never draw a landmark just because it exists.** The model returns all
  points, inventing off-frame limbs with low visibility. Gate drawing by
  visibility with hysteresis.
- **Expect ~9-15 fps with the lite model on mid-range phones.** Size throttles,
  and any timing heuristics, from measured device fps, not from the analysis
  frame rate.

## Completion criteria

On a real device: the overlay stays on the body at the frame edges in both
lenses and orientations, off-frame limbs are not drawn, the fps shown matches
expectations, and anything consuming the landmarks sees unsmoothed values.

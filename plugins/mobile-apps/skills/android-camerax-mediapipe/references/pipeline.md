# Analysis pipeline

## ImageAnalysis

```kotlin
val analysis = ImageAnalysis.Builder()
    .setResolutionSelector(
        ResolutionSelector.Builder()
            .setResolutionStrategy(ResolutionStrategy(Size(640, 480), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
            .build(),
    )
    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
    .build()
    .also { it.setAnalyzer(executor, analyzer) }   // single-thread executor
```

- A pose model needs ~640 px at most. Larger frames cost conversion time and
  give no accuracy.
- Use RGBA_8888 so `ImageProxy.toBitmap()` needs no YUV conversion code.
- Bind Preview and ImageAnalysis in the same `bindToLifecycle` call.

## Analyzer

```kotlin
override fun analyze(image: ImageProxy) {
    val now = SystemClock.uptimeMillis()
    if (now - lastSubmit < FRAME_MS || !busy.compareAndSet(false, true)) { image.close(); return }
    lastSubmit = now
    val bitmap = try { upright(image) } finally { image.close() }   // close ASAP
    frameW = bitmap.width; frameH = bitmap.height
    val ts = maxOf(now, lastTs + 1); lastTs = ts
    landmarker.detectAsync(BitmapImageBuilder(bitmap).build(), ts)
}

private fun upright(image: ImageProxy): Bitmap {
    val raw = image.toBitmap()
    val rot = image.imageInfo.rotationDegrees
    if (rot == 0) return raw
    return Bitmap.createBitmap(raw, 0, 0, raw.width, raw.height, Matrix().apply { postRotate(rot.toFloat()) }, true)
}
```

- `FRAME_MS` (e.g. 66 ms, about 15 fps) caps the work rate. The busy gate
  caps work in flight at one. On a slow phone the effective rate settles near
  the model's speed (~9 fps with lite on mid-range hardware).
- Close the `ImageProxy` before inference. Holding it stalls CameraX.
- Use `SystemClock.uptimeMillis()` for timestamps, the same clock anywhere
  else times are compared (rep windows, uploads).

## Landmarker

```kotlin
PoseLandmarker.PoseLandmarkerOptions.builder()
    .setBaseOptions(BaseOptions.builder().setModelAssetPath("pose_landmarker_lite.task").setDelegate(delegate).build())
    .setRunningMode(RunningMode.LIVE_STREAM)
    .setNumPoses(1)
    .setMinPoseDetectionConfidence(0.5f).setMinPosePresenceConfidence(0.5f).setMinTrackingConfidence(0.5f)
    .setResultListener(::onResult)
    .setErrorListener { e -> Log.w(TAG, "pose error", e); busy.set(false) }
    .build()
```

- Build with `Delegate.GPU` inside `runCatching`, then fall back to
  `Delegate.CPU`.
- Keep `.task` assets uncompressed: `androidResources { noCompress += "task" }`.
- In the result listener, clear `busy` first. Then copy x, y and visibility
  into plain float arrays and publish them through a `StateFlow`. Keep
  MediaPipe objects out of UI state.
- Always publish the frame width and height with the points. Downstream
  aspect correction depends on them, and they swap with orientation.
- On close: `analysis.clearAnalyzer()`, close the landmarker **on the
  analyzer executor** (after any in-flight frame), then shut the executor
  down.

## Recording a session

When landmarks feed a counter or an upload, gate them with `t >= startedAt`,
so that frames already queued before "start" are not counted. Create the
session lazily on the first result after start, when the frame size is known.

## Testing on real clips

Emulators have no useful camera. An instrumentation test that decodes
dataset clips, feeds frames through the exact on-device path, and writes the
results to app-private storage lets you compare the device pipeline with
desktop extraction. Pull the results with `adb pull` from
`/sdcard/Android/data/<pkg>/files/...`.

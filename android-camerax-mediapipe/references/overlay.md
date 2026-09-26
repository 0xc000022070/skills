# Overlay

## Alignment

The viewfinder fills its box and crops. Landmarks are normalized to the full
analysis frame. Map them with the same transform:

```kotlin
val s  = max(size.width / fw, size.height / fh)   // Crop = max, Fit = min
val sw = fw * s; val sh = fh * s
val ox = (size.width - sw) / 2f; val oy = (size.height - sh) / 2f
fun at(i: Int) = Offset(ox + (if (mirrored) 1f - x[i] else x[i]) * sw, oy + y[i] * sh)
```

`mirrored` is true only for the front lens. The analysis frames are never
mirrored.

Symptom: the skeleton lines up in the center but drifts toward the edges, or
is right in one screen and wrong in another. The overlay is ignoring the crop,
or it uses a different box size than the viewfinder. Put both in the same
`Box` with the same modifier.

## Smoothing (display only)

A One Euro filter per coordinate (min cutoff ~1 Hz, beta ~10). It smooths
little when a joint moves fast and a lot when it is still, so a resting joint
stops shaking and fast motion does not lag. Reset the filters when the pose
disappears.

Then ease the drawn position toward the filtered target on every display
frame (`withFrameNanos`, exponential ease with time constant ~45 ms). The
skeleton then animates at 60-120 Hz even though results arrive at ~10 Hz.

Never feed smoothed values to counters, uploads or anything a server
re-checks. The display is the only place allowed to lie.

## Visibility

- Hysteresis: show a joint at visibility >= 0.5, hide it below 0.35. A joint
  hovering around 0.5 would otherwise blink.
- Fade alpha in and out over ~120 ms, instead of popping.
- A bone's alpha is the minimum of its two joints' alphas.
- From the front, legs report ~0.15 visibility with invented positions.
  Hiding them makes the tracking look right; drawing them makes counting that
  works look broken.

## Drawing

For each bone, draw a wider dark semi-transparent line under a colored line,
with round caps, so it stays readable on any background. Joints are a white
ring with a colored dot. Draw a neck point (the shoulder midpoint) to the
nose, instead of every face landmark.

Recompose only when something moved: keep a `mutableLongStateOf` frame
counter that the step function bumps only when a position or alpha changed.

## Compose layout around the camera

- A camera box with `Modifier.weight(1f)` takes whatever the panel below it
  leaves. Measure the panel first, with a height cap.
- Inside the panel, a list with `Modifier.weight(1f, fill = false)` means "no
  taller than the space left, only as tall as needed". A long list scrolls
  instead of pushing the camera off screen, and a short one leaves no empty
  band.
- A fixed height share for the panel is the usual cause of "the bottom third
  is empty".
- Because the overlay and the viewfinder share the crop math, changing the
  camera box height keeps them aligned.

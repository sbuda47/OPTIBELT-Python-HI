# Vibration spectra — inspection release v1

In Analysis, choose **Plot type → FFT spectrum · vibration** or **Envelope spectrum · vibration**. Select a start and 2, 5 or 10 seconds, then Generate spectrum. Time waveform retains the existing native-channel viewer and its two-second segment limit.

The spectrum interval can be anywhere inside the admitted recording, independently of the playback cursor. The initial interval ends at the current playback window. Changing duration preserves that end where possible. Changing processing settings clears the old result. Display range, amplitude axis and RPM markers do not recalculate the underlying spectrum.

## FFT

Native vibration only, 25,600 samples/second, no resampling or decimation. Remove the selected segment's mean, multiply by a periodic Hann window, compute the real FFT, divide magnitude by the window sum, and double interior positive-frequency bins. DC and Nyquist are not doubled. This is **one-sided peak amplitude in native source units**, not PSD, RMS, g, velocity or dB. For a bin-centred isolated sinusoid the coherent-gain correction recovers its peak amplitude. Off-bin tones can show scalloping and leakage.

There is no zero-padding. Bin spacing is 1/duration: 0.5, 0.2 or 0.1 Hz. This does not guarantee resolving peaks that close: window main-lobe width, noise and speed changes also matter. Logarithmic mode changes the axis only; zero values are omitted from that display but retained in CSV.

## Envelope

Inspect the FFT before selecting a carrier/resonance band; no default band is represented as diagnostically correct. Both limits are required: lower at least 10 Hz, upper strictly below 12,800 Hz, and width at least 50 Hz.

The server reads up to one extra second on either side, bounded by the recording's nominal valid vibration duration. It removes the context mean, applies a Butterworth band-pass with fourth-order prototype (forward/backward SOS filtering), computes the Hilbert amplitude envelope on that context, then crops to the selected segment. It removes the envelope mean and applies the same Hann FFT amplitude scaling. Forward/backward filtering is zero-phase and squares the single-pass magnitude response. This is an **offline inspection calculation**, not a causal live HI feature.

Context reduces edge effects but does not guarantee their elimination. When context is clipped by a recording boundary, the UI warns explicitly. Band choice can materially alter results. Filter settings and context are recorded in the result and shown in Processing and source details.

## Peaks, RPM and export

Up to 20 local maxima are selected by prominence (at least 1% of the full spectrum's maximum amplitude), ranked by amplitude. The table shows the largest eight across the entire spectrum; markers show retained peaks inside the selected display range. This is a display selection rule, not a detection threshold. Endpoint bins are not local-maximum candidates.

Optional RPM is a user-supplied **constant-speed assumption**. Reference lines show 1×–10× within the displayed frequency range; table orders divide frequency by RPM/60. The feature does not estimate speed, perform order tracking or identify bearing defect frequencies. Variable-speed recordings carry a warning. No automatic fault classification is performed.

CSV exports every computed bin, regardless of zoom, with peak amplitude, recording, interval, sample rate, Hann window, bin spacing, envelope band, assumed RPM and source SHA-256. Changing log display does not alter exported amplitudes.

## Architecture and verification

`api/spectra.py` is a pure numerical module; `api/service.py` validates admission, source integrity and the native segment; POST `/api/recordings/{id}/spectrum` validates inputs. `src/components/Spectrum.tsx` manages plotting and interaction. Existing HI models, features, frozen thresholds, warm-up and alarms are unchanged.

Verification covers known-tone amplitude/frequency/DC/Nyquist, a known amplitude-modulated carrier, malformed bands, flat/nonfinite inputs, duration/bin spacing, an actual native recording compared with SciPy's independent periodogram scaling, longer segments, bounded context and HTTP input rejection. Browser checks cover real FFT/envelope, zoom, RPM markers, export, stale-result clearing, themes and mobile width. Numerical tests validate implementation; these recordings do not establish diagnostic accuracy.

Deployment keeps a pre-spectrum copy in `archive/` for rollback. To roll back, stop this dashboard's listener, restore that archive's `api`, `src`, `dist` and documentation to `web_dashboard`, then run `start-web-dashboard.ps1`. Do not alter the research or Streamlit environments.

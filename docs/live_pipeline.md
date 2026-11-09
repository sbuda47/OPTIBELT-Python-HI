# Simulated-live pipeline — 9 November 2026

A separate raw-data pipeline is implemented in `live_pipeline/`. It accepts atomic timestamped five-channel packets, processes buffered FIR/current resampling and two-second features, and uses the unchanged C reference and operator alarm policy. Recording-based simulation, local API, engineering status page and session journals work without hardware.

See [setup, architecture and acquisition contract](../live_pipeline/README.md) and [verification evidence](../live_pipeline/verification/validation.json).

Verification: 17 lifecycle/API checks passed; healthy and bearing-fault raw replays matched offline alarm decisions; real-time browser simulation continued through the critical popup. Stopping input blanks current HI and preserves the latch. Restart recovery and recovered-state acknowledgement are tested. The monitor is available locally on port 8766; original playback remains separate on port 8765.

This advances Q15 from a resampling prototype to an integrated simulated-live software path. It does not resolve physical sensor scaling, hardware synchronization, real load transitions, independent acquisition validation, deployment reliability or target-device timing. No model refitting, HP-specific modelling or automatic motor stopping was introduced.

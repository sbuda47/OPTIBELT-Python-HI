# Current scientific and software status

As of 9 November 2026, retain the two-second load-aware full-fusion candidate and existing operator policy. No HP-specific fitted models or automatic motor stops.

| Question | Evidence | Limit |
|---|---|---|
| Calculations correct? | Independent resampling/moments/FFT/MD checks and frozen-result reproduction passed | This does not establish physical sensor calibration |
| Available fault response? | C: 10/11 confirmed critical requests in supported reserved checks; all 11 non-normal | Existing recordings influenced development |
| Healthy behavior? | No critical requests in 17 healthy recordings; 2 warning records in check scope and 4 in full replay | Limited exposed duration is not a deployment false-alarm rate |
| Two shorter faults? | Separate 120/31-second replay confirmed both | Acquisition discrepancies and physical onset remain unresolved |
| Fusion complexity? | Full fusion 10/11 critical requests; vibration/current alone each 4/11; vibration+torque 9/11 using 17 rather than 36 retained features | Trade-off under this subset/procedure, not universal superiority |
| Window sensitivity? | Matched checks: 1/2/4 seconds all confirm 10/11; healthy warning steps 37/24/0 | Four seconds adds collection delay; new/brief-fault latency unknown |
| Native current bandwidth? | Native 100 kHz variant still confirms 10/11 | Changed bandwidth/statistics together; no general proof high frequencies are uninformative |
| Streaming feasibility? | Bounded FIR, small startup differences, matching tested alarm outcomes; integrated simulator/API tested | No physical acquisition or deployment validation |

References: `reproducibility/reference/` contains numerical tables. Ablations use 570 healthy/255 faulty eligible steps; matched sampling uses 536/233. Keep denominators and scopes separate. The independent-acquisition test remains future work; copying files or splitting more windows does not create independence.

The other documents retain protocols, decisions and dated historical findings. Early statements such as “no fitted model” describe past milestones, not today's state. `docs/history/workspace_milestones.md` preserves the original chronological README. Use this file and the reproduction guide as the current entry points.

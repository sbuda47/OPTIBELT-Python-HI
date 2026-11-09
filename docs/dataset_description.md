# Source data and admission record

The starting dataset consists of the 41 local MAT recordings previously linked to the final-year project. dataset/manifests/copy_receipt.csv records the original path, SHA-256, size and copy time. Files remain byte-identical to their source copies.

The supplied [Mendeley page](https://data.mendeley.com/datasets/gr8c9ckhxh/3), DOI 10.17632/gr8c9ckhxh.3, describes AC.z05, one volume of a seven-part archive. It reports a CC BY 4.0 licence. The locally extracted recordings predate this page's version-3 publication on 17 August 2026. Their identity with that particular archive version has not been established. No new archive download is part of this milestone.

The source article is Wonho Jung et al., *Vibration, current, torque, RPM dataset for multiple fault conditions in industrial-scale electric motors under randomized speed and load variations*, Data in Brief 62 (2025), 111954. [Publisher record](https://www.sciencedirect.com/science/article/pii/S235234092500678X)

## Rates and representation

The article's page 5 and Table 3 report vibration and torque at 25,600 samples/second, and three-phase current at 100,000 samples/second. Nominal durations are 300 seconds for invariant speed and 120 seconds for varying speed.

The local files contain one numeric variable named data. Column order is taken from the recovered extraction code and supported by the observed finite-prefix lengths
1. Vibration
2. Torque
3. R-phase current
4. S-phase current
5. T-phase current

Equal row indices across these columns do not represent equal elapsed time. The lower-rate channels end earlier in the matrix and use NaN padding. Each native channel must be interpreted at its own rate. A complete 120-second file has 3,072,000 native vibration/torque samples and 12,000,000 samples per current phase.

The paper calls the time series synchronized. This supports a provisional common-start assumption. There are no explicit timestamps in the inspected data matrices, and exact inter-device offsets have not been independently measured.

## Labels

Filename motor capacity and load are separate fields. The final percentage token is the load label. In Coil60%_3HP_30%, the 60% describes fault severity and 30% describes load. Coil and Interturn are retained as separate source labels. Unknown conditions cause an error.

For varying-speed filenames, 52Hz and 58Hz describe the upper bound of a randomized supply-frequency profile starting at 50 Hz. They are not treated as constant instantaneous supply frequencies.

Load is a source label. It has not been estimated from torque. Motor capacity is retained, while physical motor identity and acquisition run identity remain unknown. All severities retain their literal source spelling until units and fault definitions are checked against the article's tables and figures.

The 7.5 HP unit was modified for journal-bearing faults. That subset needs special treatment when evaluating transfer from healthy motors of other ratings.

## Sensor documentation

The article describes PCB352C34 accelerometers for constant-speed runs and PCB356A45 for variable-speed runs, Hioki CT7731 current sensors, a SETech YDR 2 K torque meter, and NI 9234/9215 modules on a cDAQ-9185 chassis. These are source descriptions. Local columns do not embed calibration certificates or channel units.

## Scope of the integrity audit

The audit checks file hashes, MAT readability, dimensions, dtype, finite samples, per-channel ranges, constant channels and padding. It never interpolates missing measurements. Signal quality flags are evidence for data admission, not automatic diagnoses of sensor failure.


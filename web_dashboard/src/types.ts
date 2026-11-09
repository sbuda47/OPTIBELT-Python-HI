export type Reference='C'|'A';
export type Duration=2|3|5;
export type View='Operator'|'Analysis'|'Event log';
export interface Recording {id:string;hp:number;load:number;profile:string;condition:string;duration:number;windows:number;start:number;end:number;source:string}
export interface Catalogue {recordings:Recording[];candidate:string;policy:string;channels:string[];evidence:string;motor_telemetry:boolean}
export interface Row {episode_window_index:number;stop_seconds:number;distance:number;distance_ewma:number;operator_hi:number;operator_hi_raw:number;eligible:boolean;zone_state:string;instantaneous_zone:string|null;data_valid:boolean;critical_elapsed_seconds:number;new_operator_alarm:boolean;operator_alarm_latched:boolean;acknowledged:boolean}
export interface Event {window:number;record_seconds:number;event:string;operator_hi:number}
export interface Playback {recording_id:string;reference:Reference;confirmation_seconds:Duration;rows:Row[];events:Event[];candidate:string;policy:string;motor_stop_command:boolean}
export interface Signal {recording_id:string;channel:string;times:number[];values:number[];rate:number;smoothed:number[]|null;smooth_ms:number|null;source:string;sha256:string;units:string;decimated:boolean}
export interface Notice {token:string;confirmed:boolean;row:Row}
export interface SpectrumResult {
 recording_id:string;mode:'fft'|'envelope';frequencies:number[];amplitudes:number[];
 peaks:{frequency_hz:number;amplitude:number}[];rate:number;sample_count:number;
 bin_spacing_hz:number;nyquist_hz:number;units:string;scaling:string;window:string;
 processing:string[];band_hz:number[]|null;start_seconds:number;end_seconds:number;seconds:number;
 context_before_seconds:number;context_after_seconds:number;source:string;sha256:string;
 warnings:string[];peak_selection:string;
}

type Wave = OscillatorType;

export type AlertTone =
  | "warning"      // generic threshold warning
  | "critical"     // automatic safe-stop
  | "seatbelt"     // seatbelt on → off
  | "verified"     // task completed / work done / verified settle
  | "fuel"         // FUEL_LEAK / abnormal fuel loss
  | "overheat"     // ENGINE_OVERHEAT
  | "hydraulic"    // HYDRAULIC_FAILURE
  | "proximity"    // PROXIMITY_HAZARD
  | "idle"         // EXCESSIVE_IDLE
  | "unsafe"       // UNSAFE_OPERATION
  | "sensor"       // SENSOR_FAILURE
  | "battery"      // BATTERY_ANOMALY
  | "multi"        // MULTI_FACTOR_INCIDENT
  | "help"         // help requested / acknowledged
  | "confirm";     // operator action applied

type Note = [frequency: number, duration: number];
interface Pattern {
  wave: Wave;
  notes: Note[];
  gap: number;
  volume: number;
}

let audioContext: AudioContext | null = null;

function context() {
  if (typeof window === "undefined") return null;
  audioContext ??= new AudioContext();
  void audioContext.resume();
  return audioContext;
}

function beep(ctx: AudioContext, wave: Wave, frequency: number, start: number, duration: number, volume: number) {
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = wave;
  oscillator.frequency.value = frequency;
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  oscillator.connect(gain).connect(ctx.destination);
  oscillator.start(start);
  oscillator.stop(start + duration + 0.02);
}

const PATTERNS: Record<AlertTone, Pattern> = {
  // flat double-pulse — threshold crossed
  warning: { wave: "square", notes: [[660, 0.09], [660, 0.09]], gap: 0.14, volume: 0.028 },
  // rising alert climb — auto safe-stop engage
  critical: { wave: "sawtooth", notes: [[392, 0.12], [523, 0.12], [784, 0.18]], gap: 0.1, volume: 0.035 },
  // dull wobble down — belt discipline
  seatbelt: { wave: "sine", notes: [[520, 0.11], [392, 0.11], [520, 0.11], [330, 0.18]], gap: 0.09, volume: 0.04 },
  // bright two-note resolve — job done
  verified: { wave: "square", notes: [[660, 0.09], [880, 0.09], [1100, 0.2]], gap: 0.08, volume: 0.03 },
  // liquid descending blips — fuel leak
  fuel: { wave: "sine", notes: [[880, 0.1], [587, 0.1], [262, 0.1], [196, 0.24]], gap: 0.12, volume: 0.04 },
  // hot boil shimmer — overheat
  overheat: { wave: "triangle", notes: [[311, 0.1], [466, 0.1], [622, 0.1], [466, 0.1], [311, 0.2]], gap: 0.08, volume: 0.035 },
  // heavy pump clunk — hydraulics
  hydraulic: { wave: "square", notes: [[196, 0.22], [165, 0.22], [147, 0.28]], gap: 0.12, volume: 0.04 },
  // rapid ping ramp — proximity warning
  proximity: { wave: "square", notes: [[880, 0.06], [880, 0.06], [880, 0.06], [1100, 0.16]], gap: 0.06, volume: 0.03 },
  // slow drone pair — excessive idle
  idle: { wave: "sine", notes: [[220, 0.2], [196, 0.2], [174, 0.3]], gap: 0.12, volume: 0.032 },
  // two clipped stabs — unsafe operation
  unsafe: { wave: "sawtooth", notes: [[330, 0.1], [330, 0.1], [247, 0.24]], gap: 0.09, volume: 0.04 },
  // glitchy triple — sensor failure
  sensor: { wave: "square", notes: [[523, 0.08], [440, 0.08], [523, 0.08], [494, 0.18]], gap: 0.07, volume: 0.035 },
  // cold drop — battery anomaly
  battery: { wave: "triangle", notes: [[440, 0.14], [349, 0.14], [262, 0.28]], gap: 0.1, volume: 0.035 },
  // layered alarm — multi-factor
  multi: { wave: "sawtooth", notes: [[523, 0.1], [392, 0.1], [659, 0.1], [523, 0.1], [784, 0.24]], gap: 0.08, volume: 0.04 },
  // relay ping — help opened/answered
  help: { wave: "square", notes: [[784, 0.08], [988, 0.08], [1175, 0.18]], gap: 0.08, volume: 0.028 },
  // single accept blip — action applied
  confirm: { wave: "square", notes: [[660, 0.09], [880, 0.14]], gap: 0.1, volume: 0.03 },
};

export const toneForIncident = (incidentType: string): AlertTone => {
  const key = incidentType.toUpperCase().replace(/[^A-Z_]/g, "");
  switch (key) {
    case "FUEL_LEAK": return "fuel";
    case "ENGINE_OVERHEAT": return "overheat";
    case "HYDRAULIC_FAILURE": return "hydraulic";
    case "PROXIMITY_HAZARD": return "proximity";
    case "SEATBELT_VIOLATION": return "seatbelt";
    case "EXCESSIVE_IDLE": return "idle";
    case "UNSAFE_OPERATION": return "unsafe";
    case "SENSOR_FAILURE": return "sensor";
    case "BATTERY_ANOMALY": return "battery";
    case "MULTI_FACTOR_INCIDENT": return "multi";
    default: return "warning";
  }
};

export function playAlertTone(tone: AlertTone) {
  const ctx = context();
  if (!ctx) return;
  const { wave, notes, gap, volume } = PATTERNS[tone];
  let cursor = ctx.currentTime;
  for (const [frequency, duration] of notes) {
    beep(ctx, wave, frequency, cursor, duration, volume);
    cursor += duration + gap;
  }
}
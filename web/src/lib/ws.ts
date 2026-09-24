import { wsUrl } from "./api";
import type { TelemetryFrame, WsMessage } from "./types";

type Listener = (msg: WsMessage) => void;

/**
 * WebSocket client that batches incoming frames and flushes them on the next
 * animation frame, so chart rendering stays ≤ display refresh no matter how
 * fast the simulator emits.
 */
export class TelemetrySocket {
  private ws: WebSocket | null = null;
  private queue: TelemetryFrame[] = [];
  private rafId: number | null = null;
  private reconnectTimer: number | null = null;
  private closed = false;

  constructor(private machineId: string, private onFrame: (frames: TelemetryFrame[]) => void) {}

  connect(onStatus: (connected: boolean) => void, onMessage?: Listener) {
    this.closed = false;
    const open = () => {
      const ws = new WebSocket(wsUrl(this.machineId));
      this.ws = ws;

      ws.onopen = () => onStatus(true);
      ws.onclose = () => {
        onStatus(false);
        if (!this.closed) {
          this.reconnectTimer = window.setTimeout(open, 1500);
        }
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as WsMessage;
          if (msg.type === "frame" && msg.frame) {
            this.queue.push(msg.frame);
            if (this.rafId === null) {
              this.rafId = requestAnimationFrame(() => {
                const batch = this.queue;
                this.queue = [];
                this.rafId = null;
                if (batch.length > 0) this.onFrame(batch);
              });
            }
          }
          onMessage?.(msg);
        } catch {
          /* ignore malformed frames */
        }
      };
    };
    open();
  }

  close() {
    this.closed = true;
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.ws?.close();
  }

  send(obj: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }
}
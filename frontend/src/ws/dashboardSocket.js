// Client WebSocket per /ws/dashboard/{run_id} (vedi docs/api.md). Canale in
// sola ricezione: riceve un evento "measurement" per ogni misura scritta con
// successo su quel Run, da qualunque fonte (Edge Agent o inserimento manuale).
import { API_BASE } from "../api/client";
import { useAuthStore } from "../stores/auth";

const RECONNECT_DELAYS_MS = [500, 1000, 2000, 4000, 8000]; // poi resta a 8s

export function connectDashboardSocket(runId, onMessage) {
  const auth = useAuthStore();
  let socket = null;
  let attempt = 0;
  let closedByCaller = false;
  let reconnectTimer = null;

  function wsUrl() {
    const httpBase = API_BASE || window.location.origin;
    const wsBase = httpBase.replace(/^http/, "ws");
    return `${wsBase}/ws/dashboard/${runId}?token=${encodeURIComponent(auth.accessToken || "")}`;
  }

  function connect() {
    socket = new WebSocket(wsUrl());
    socket.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch {
        // messaggio non JSON: ignorato, non dovrebbe succedere con questo protocollo
      }
    };
    socket.onclose = () => {
      if (closedByCaller) return;
      const delay = RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)];
      attempt += 1;
      reconnectTimer = setTimeout(connect, delay);
    };
    socket.onopen = () => {
      attempt = 0;
    };
  }

  connect();

  return {
    close() {
      closedByCaller = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    },
  };
}

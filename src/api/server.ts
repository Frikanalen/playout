import { WebSocket, WebSocketServer } from "ws";
import { log } from "../log.js";
import { timeline } from "../scheduling/Timeline.js";
import { getRemoteAddress } from "./getRemoteAddress.js";
import type { IncomingMessage } from "http";

const UPDATE_INTERVAL_MS = 200 as const;
let updateTimer: NodeJS.Timer | null = null;
let wsServer: WebSocketServer | null = null;

const sendUpdate = () => {
  if (!wsServer) {
    log.warn(`sendUpdate called with no wsServer - shouldn't happen`);
    if (updateTimer) {
      log.warn(`update timer still running - shouldn't happen - clearing it`);
      clearInterval(updateTimer);
    }
    return;
  }

  if (!wsServer.clients.size) {
    if (updateTimer) {
      log.debug(`No websocket clients connected, clearing update timer`);
      clearInterval(updateTimer);
    }
    return;
  }

  const now = new Date();
  const message = JSON.stringify({
    time: now.toISOString(),
    timeline: timeline.getItems(),
  });

  wsServer.clients.forEach((sock) => sock.send(message));
};
const handleConnection = (sock: WebSocket, incoming: IncomingMessage) => {
  log.info(`Websocket client connected from ${getRemoteAddress(incoming)}`);

  sendUpdate();
  if (!updateTimer) updateTimer = setInterval(sendUpdate, UPDATE_INTERVAL_MS);

  sock.on("error", log.error);

  sock.on("close", (code, reason) => {
    log.info(`Websocket client disconnected (${code}, reason: "${reason}")`);
  });

  sock.on("message", (data: any) => {
    log.warn(`Received message ${data} on read-only socket`);
  });
};

export const startWebsocketServer = (port: number) => {
  log.info(`Starting websocket server on port ${port}`);
  wsServer = new WebSocketServer({ port: port });
  wsServer.on("connection", handleConnection);
};

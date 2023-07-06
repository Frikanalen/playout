import { WebSocket, WebSocketServer } from "ws";
import { log } from "./log.js";
import { timeline } from "./scheduling/Timeline.js";
import { getRemoteAddress } from "./api/getRemoteAddress.js";
import type { IncomingMessage } from "http";

const UPDATE_INTERVAL_MS = 200 as const;
let updateTimer: NodeJS.Timer | null = null;
let wsServer: WebSocketServer | null = null;

const sendUpdate = () => {
  if (!wsServer) {
    log.warn(`Websocket server not initialized`);
    return;
  }

  if (!wsServer.clients.size) {
    if (updateTimer) clearInterval(updateTimer);
    return;
  }

  const now = new Date();
  const message = JSON.stringify({
    time: now.toISOString(),
    timeline: timeline.getItems(),
  });

  wsServer.clients.forEach((sock) => sock.send(message));
};
const handleConnection = (wsSocket: WebSocket, incoming: IncomingMessage) => {
  log.info(`Websocket client connected from ${getRemoteAddress(incoming)}`);

  sendUpdate();
  if (!updateTimer) updateTimer = setInterval(sendUpdate, UPDATE_INTERVAL_MS);

  wsSocket.on("error", log.error);

  wsSocket.on("close", () => {
    log.info(`Websocket client disconnected`);
  });

  wsSocket.on("message", (data: any) => {
    log.warn(`Received message ${data} on read-only socket`);
  });
};

export const startWebsocketServer = () => {
  wsServer = new WebSocketServer({ port: 8080 });
  wsServer.on("connection", handleConnection);
};

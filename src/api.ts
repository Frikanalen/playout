import { WebSocketServer, WebSocket } from "ws";
import { log } from "./log.js";

const wsServer = new WebSocketServer({ port: 8080 });

const clients: WebSocket[] = [];

let updateTimer: NodeJS.Timer | null = null;

const sendUpdate = () => {
  const now = new Date();
  const message = JSON.stringify({
    time: now.toISOString(),
  });

  clients.forEach((sock) => sock.send(message));
};

// If any clients are connected, send an update every 250 ms.
const setOrClearInterval = () => {
  if (clients.length && !updateTimer) {
    updateTimer = setInterval(sendUpdate, 250);
  } else if (!clients.length && updateTimer) {
    clearInterval(updateTimer);
    updateTimer = null;
  } else {
    log.warn("unexpected state in setOrClearInterval");
  }
};

wsServer.on("connection", (wsSocket) => {
  clients.push(wsSocket);
  setOrClearInterval();

  wsSocket.on("error", log.error);

  wsSocket.on("close", () => {
    const index = clients.indexOf(wsSocket);
    if (index > -1) clients.splice(index, 1);
    setOrClearInterval();
  });

  wsSocket.on("message", (data) => {
    log.warn(`Received message ${data} on read-only socket`);
  });
});

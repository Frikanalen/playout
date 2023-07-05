import { WebSocketServer, WebSocket } from "ws";
import { log } from "./log.js";

const wsServer = new WebSocketServer({ port: 8080 });

const wsConnections: WebSocket[] = [];

let updateTimer: NodeJS.Timer | null = null;

// If any clients are connected, send an update every 250 ms.
const setOrClearInterval = () => {
  if (wsConnections.length && !updateTimer) {
    updateTimer = setInterval(() => {
      wsConnections.forEach((wsSocket) => {
        wsSocket.send("something");
      });
    }, 250);
  } else if (!wsConnections.length && updateTimer) {
    clearInterval(updateTimer);
    updateTimer = null;
  } else {
    log.warn("unexpected state in setOrClearInterval");
  }
};

wsServer.on("connection", (wsSocket) => {
  wsConnections.push(wsSocket);
  setOrClearInterval();

  wsSocket.on("error", log.error);

  wsSocket.on("close", () => {
    const index = wsConnections.indexOf(wsSocket);
    if (index > -1) wsConnections.splice(index, 1);
    setOrClearInterval();
  });

  wsSocket.on("message", (data) => {
    log.warn(`Received message ${data} on read-only socket`);
  });
});

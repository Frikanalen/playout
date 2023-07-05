import { WebSocketServer, WebSocket } from "ws";
import { log } from "./log.js";

const wsServer = new WebSocketServer({ port: 8080 });

const wsConnections: WebSocket[] = [];

wsServer.on("connection", (wsSocket) => {
  wsConnections.push(wsSocket);

  wsSocket.on("error", log.error);

  wsSocket.on("message", (data) => {
    log.warn(`Received message ${data} on read-only socket`);
  });

  wsSocket.send("something");
});

import type { IncomingMessage } from "http";

// If the incomingMessage includes X-Forwarded headers, we can use those
// to determine the client's IP address. Otherwise, we can use the
// remoteAddress property of the socket.
export const getRemoteAddress = (incoming: IncomingMessage) => {
  return incoming.headers["x-forwarded-for"]
    ? [...incoming.headers["x-forwarded-for"]].join(";")
    : incoming.socket.remoteAddress!;
};

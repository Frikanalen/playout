import { Logger } from "tslog";

const isProduction = process.env.NODE_ENV === "production";

let log: Logger<unknown>;

if (isProduction) {
  log = new Logger({ type: "json" });
} else {
  log = new Logger({ type: "pretty" });
}

export { log };

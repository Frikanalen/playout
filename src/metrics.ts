import { createServer } from "http";
import { Gauge, register } from "prom-client";
import { timeline } from "./scheduling/Timeline.js";

// Create a new Gauge metric
const scheduledItems = new Gauge({
  name: "scheduled_items",
  help: "Number of scheduled jobs",
});

// Create a server to serve the metrics
createServer((req, res) => {
  if (req.url === "/metrics") {
    scheduledItems.set(timeline.getEvents().length);

    res.setHeader("Content-Type", "text/plain");
    res.end(register.metrics());
  } else {
    res.end();
  }
}).listen(9000);

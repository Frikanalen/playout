import { createServer } from "http";
import { Gauge, register } from "prom-client";
import schedule from "node-schedule";

// Create a new Gauge metric
const scheduledItems = new Gauge({
  name: "scheduled_items",
  help: "Number of scheduled jobs",
});

// Function to update the metric
function updateScheduledItemsMetric() {
  const jobs = Object.keys(schedule.scheduledJobs).length;
  scheduledItems.set(jobs);
}

// Create a server to serve the metrics
createServer((req, res) => {
  if (req.url === "/metrics") {
    updateScheduledItemsMetric();
    res.setHeader("Content-Type", "text/plain");
    res.end(register.metrics());
  } else {
    res.end();
  }
}).listen(9000);

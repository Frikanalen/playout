import { FK_API } from "./config.js";
import { SchedulingService } from "./generated/index.js";
import { endOfDay, startOfDay } from "date-fns";
import process from "node:process";
import { log } from "./log.js";
import { makeTestSchedule } from "./scheduling/testUtils.js";

// Get schedule from API if configured, otherwise use test schedule.
// As a safety measure, throws an error if no API is configured in production.
export const getSchedule = async () => {
  const now = new Date();

  if (FK_API) {
    return SchedulingService.getSchedule(
      startOfDay(now).toISOString(),
      endOfDay(now).toISOString(),
    );
  } else {
    if (process.env["NODE_ENV"] === "production")
      throw new Error("No API configured");

    log.warn("No API configured, using test schedule");

    return makeTestSchedule(
      startOfDay(now).toISOString(),
      endOfDay(now).toISOString(),
    );
  }
};

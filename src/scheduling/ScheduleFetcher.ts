import { SchedulingService } from "../generated/index.js";
import { log } from "../log.js";

export const fetchSchedule = async (start: Date, end: Date) => {
  const schedule = await SchedulingService.getSchedule(
    start.toISOString(),
    end.toISOString()
  );

  if (!schedule.length)
    throw new Error(
      `Schedule for ${start.toISOString()}-${end.toISOString()} contains 0 items!`
    );

  log.info(`Schedule loaded ${schedule.length} items.`);

  return schedule;
};

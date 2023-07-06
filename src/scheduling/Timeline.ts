import schedule, { Job } from "node-schedule";
import { compactTimestamp } from "./ScheduleLoader.js";
import type { ScheduleItem } from "./ScheduleLoader.js";
import { log } from "../log.js";

export type JobDescriptor = {
  item: ScheduleItem;
  fireAt: Date;
  eventLabel: string;
  job: Job;
};

export class Timeline {
  private events: JobDescriptor[] = [];
  private items: ScheduleItem[] = [];

  addItem = async (item: ScheduleItem) => {
    await item.arm();
    this.items.push(item);
  };

  addEvent = (
    item: ScheduleItem,
    fireAt: Date,
    eventLabel: string,
    cb: (firedAt: Date, ...rest: any[]) => Promise<void>
  ) => {
    const invokeCallback = async (firedAt: Date, ...rest: any[]) => {
      log.info(`Firing ${eventLabel} at ${compactTimestamp(item)}`);
      await cb(firedAt, { ...rest });
    };

    const job = schedule.scheduleJob(fireAt, invokeCallback);
    this.events.push({ item, fireAt, eventLabel, job });
    this.events.sort((a, b) => a.fireAt.getTime() - b.fireAt.getTime());
  };

  clear = async () => {
    log.info("Clearing timeline jobs");
    await Promise.all(this.events.map(({ job }) => job.cancel()));
    this.events = [];
  };

  // Remove all jobs belonging to given ScheduleItem
  remove = async (item: ScheduleItem) => {
    log.info(`Removing jobs for ${compactTimestamp(item)}`);
    const jobsToRemove = this.events.filter((job) => job.item === item);
    await Promise.all(jobsToRemove.map(({ job }) => job.cancel()));
    this.events = this.events.filter((job) => job.item !== item);
  };

  // Return a list of all timeline entries
  getEvents = () => this.events;

  getItems = () => this.items;

  // Run until the last job is finished
  run = () => {
    log.info("Running timeline");
    return new Promise<void>((resolve) => {
      const lastJob = this.events[this.events.length - 1];

      if (!lastJob) {
        log.info("No jobs in timeline");
        resolve();
        return;
      }

      lastJob.job.on("run", () => {
        log.info("Timeline finished");
        resolve();
      });
    });
  };
}
export const timeline = new Timeline();

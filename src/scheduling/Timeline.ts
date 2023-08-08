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
    this.items.sort((a, b) => a.startsAt.getTime() - b.startsAt.getTime());
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

  clear = () => {
    log.info("Clearing timeline jobs");
    this.events.forEach(({ job }, index) => {
      // Here a race condition-like problem was encountered which crashed the playout.
      // One failed assumption was that the job.cancel() method would be asynchronous,
      // so I iterated over them with Promise.all().
      //
      // However, an exception arose that job == null, which was unexpected.
      //
      // The logic has been changed to iterate over the jobs synchronously, and
      // both the unexpected and expected cases are logged for more context
      // should the issue arise again.
      if (!job?.cancel) {
        log.warn(
          `Job ${index + 1}/${this.events.length} ` +
            `(${job?.name}) has no cancel method`
        );
        return;
      }

      log.info(
        `Cancelling job ${index + 1}/${this.events.length} (${job?.name})`
      );

      job.cancel();
    });

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

    return new Promise<void>((resolve, reject) => {
      const lastJob = this.events[this.events.length - 1];

      if (!lastJob) {
        log.info("No jobs in timeline");
        reject();
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

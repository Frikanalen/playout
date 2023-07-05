import schedule, { Job } from "node-schedule";
import { compactTimestamp, ScheduleItem } from "./Schedule.js";
import { log } from "../log.js";

export type JobDescriptor = {
  item: ScheduleItem;
  fireAt: Date;
  eventLabel: string;
  job: Job;
};

export class Timeline {
  private timelineItems: JobDescriptor[] = [];

  add = (
    item: ScheduleItem,
    fireAt: Date,
    eventLabel: string,
    cb: (firedAt: Date, ...rest: any[]) => Promise<void>
  ) => {
    const job = schedule.scheduleJob(
      fireAt,
      async (firedAt, ...rest: any[]) => {
        log.info(`Firing ${eventLabel} at ${compactTimestamp(item)}`);
        await cb(firedAt, { ...rest });
      }
    );
    this.timelineItems.push({ item, fireAt, eventLabel, job });
    this.timelineItems.sort((a, b) => a.fireAt.getTime() - b.fireAt.getTime());
  };

  clear = async () => {
    log.info("Clearing timeline jobs");
    await Promise.all(this.timelineItems.map(({ job }) => job.cancel()));
    this.timelineItems = [];
  };

  // Remove all jobs belonging to given ScheduleItem
  remove = async (item: ScheduleItem) => {
    log.info(`Removing jobs for ${compactTimestamp(item)}`);
    const jobsToRemove = this.timelineItems.filter((job) => job.item === item);
    await Promise.all(jobsToRemove.map(({ job }) => job.cancel()));
    this.timelineItems = this.timelineItems.filter((job) => job.item !== item);
  };

  // Return a list of all timeline entries
  getTimeline = () => this.timelineItems;

  // Run until the last job is finished
  run = () => {
    log.info("Running timeline");
    return new Promise<void>((resolve) => {
      const lastJob = this.timelineItems[this.timelineItems.length - 1];

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

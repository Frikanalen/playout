import nodeSchedule from "node-schedule";
import { add, format, sub, subMilliseconds } from "date-fns";
import { CG_LAYER, GRAPHICS_URL } from "../config.js";
import { log } from "../log.js";
import { connection } from "../connection.js";
import { ScheduleItem } from "./Schedule.js";

const wait = async (ms: number) =>
  new Promise((resolve) => setTimeout(resolve, ms));

export class InterstitialGraphics implements ScheduleItem {
  private jobs: nodeSchedule.Job[];

  getJobs() {
    return this.jobs;
  }

  compactTimestamp() {
    const { startsAt, endsAt } = this;

    return `${format(startsAt, "HH:mm:ss.SSx")} - ${format(
      endsAt,
      "HH:mm:ss.SSx"
    )}`;
  }

  constructor(private startsAt: Date, private endsAt: Date) {
    this.jobs = [];
  }

  async load() {
    log.info(`CG loading, URL: ${GRAPHICS_URL}`);

    await connection.cgAdd({
      ...CG_LAYER,
      template: GRAPHICS_URL,
      playOnLoad: false,
    });
  }

  async play() {
    log.info(`Playing CG`);

    await connection.cgPlay(CG_LAYER);
  }

  async stop() {
    log.info(`Stopping CG`);

    await connection.cgStop(CG_LAYER);
  }

  async clear() {
    log.info(`Clearing CG`);
    await connection.cgClear(CG_LAYER);
  }

  async arm() {
    const now = new Date();
    const { startsAt, endsAt, load, play, stop, clear } = this;
    const loadAt = sub(startsAt, { seconds: 1 });
    const playAt = subMilliseconds(startsAt, 500);
    const clearAt = add(endsAt, { seconds: 2 });

    if (endsAt <= now) {
      log.debug(`Not scheduling graphics {${endsAt} is in the past)`);
      return;
    }

    if (startsAt <= now) {
      log.warn(`Graphics ${this.compactTimestamp()} should be running`);

      log.info(`Arming graphics for ${this.compactTimestamp()}`);
      await load();
      // Wait a second before playing to allow the CG to load
      await wait(1000);

      log.info(`Playing graphics for ${this.compactTimestamp()}`);
      await play();

      this.jobs = [
        nodeSchedule.scheduleJob(endsAt, stop),
        nodeSchedule.scheduleJob(clearAt, clear),
      ];
    } else {
      log.debug(`Arming graphics for ${this.compactTimestamp()}`);

      this.jobs = [
        nodeSchedule.scheduleJob(loadAt, load),
        nodeSchedule.scheduleJob(playAt, play),
        nodeSchedule.scheduleJob(endsAt, stop),
        nodeSchedule.scheduleJob(clearAt, clear),
      ];
    }
  }

  async disarm() {
    for (const job of this.jobs) {
      job.cancel();
    }
  }
}

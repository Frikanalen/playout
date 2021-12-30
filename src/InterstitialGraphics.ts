import nodeSchedule from "node-schedule";
import { add, format, sub, subMilliseconds } from "date-fns";
import { GRAPHICS_URL } from "./config";
import { Schedulable } from "./Schedulable";
import { connection, log } from ".";

export class InterstitialGraphics implements Schedulable {
  private jobs: nodeSchedule.Job[];

  compactTimestamp() {
    const { startsAt, endsAt } = this;

    return format(startsAt, "HH:mm:ss.SSx - ") + format(endsAt, "HH:mm:ss.SSx");
  }

  constructor(private startsAt: Date, private endsAt: Date) {
    this.jobs = [];
  }

  async load() {
    log.info(`CG loading, URL: ${GRAPHICS_URL}`);

    await connection.cgAdd(1, 100, 0, GRAPHICS_URL, false);
  }

  async play() {
    log.info(`Playing CG`);

    await connection.cgPlay(1, 100, 0);
  }

  async stop() {
    log.info(`Stopping CG`);

    await connection.cgStop(1, 100, 0);
  }

  async clear() {
    log.info(`Clearing CG`);

    await connection.cgClear(1, 100);
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

      await load();
      setTimeout(async () => {
        await play();
      }, 1000);

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

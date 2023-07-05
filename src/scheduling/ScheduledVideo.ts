import { differenceInSeconds, format, sub } from "date-fns";
import { ScheduleEntry } from "../generated/index.js";
import {
  CASPAR_MEDIA_URL_PREFIX,
  CHANNEL_FPS,
  VIDEO_LAYER,
} from "../config.js";
import nodeSchedule from "node-schedule";
import { log } from "../log.js";
import { connection } from "../connection.js";
import { ScheduleItem } from "./Schedule.js";

export class ScheduledVideo implements ScheduleItem {
  private jobs: nodeSchedule.Job[];
  startsAt: Date;
  endsAt: Date;
  videoTitle: string;

  constructor(private entry: ScheduleEntry) {
    this.startsAt = new Date(entry.startsAt);
    this.endsAt = new Date(entry.endsAt);
    this.videoTitle = entry.video.title!;
    this.jobs = [];
  }

  getJobs() {
    return this.jobs;
  }

  compactTimestamp() {
    const { startsAt, endsAt } = this;

    return format(startsAt, "HH:mm:ss.SSx - ") + format(endsAt, "HH:mm:ss.SSx");
  }

  getFilename() {
    const asset = this.entry.video.media!.assets!.find(
      (x) => x.type === "broadcastable"
    )!.url;

    return CASPAR_MEDIA_URL_PREFIX + asset;
  }

  loadbg = async () => {
    log.info(`Loading video "${this.entry.video.title}"`);

    await connection.loadbg({ ...VIDEO_LAYER, clip: this.getFilename() });
  };

  stop = async (_: Date) => {
    log.info(`Stopping video "${this.entry.video.title}"`);

    await connection.stop(VIDEO_LAYER);
  };

  play = async (firedAt: Date, seekSeconds: number = 0) => {
    const seek = seekSeconds ? seekSeconds * CHANNEL_FPS : undefined;

    log.info(`Playing video "${this.entry.video.title}"`);

    await connection.play({
      ...VIDEO_LAYER,
      clip: this.getFilename(),
      seek,
    });
  };

  async arm() {
    const { startsAt, endsAt, stop, play, loadbg, videoTitle } = this;

    const now = new Date();

    if (endsAt <= now) {
      log.debug(`Not scheduling video (${endsAt} is in the past)`);
      return;
    }

    if (startsAt <= now) {
      log.warn(`timer was armed while program should be active`);
      const requiredSeek = differenceInSeconds(now, startsAt);
      log.info(`playing immediately and seeking ${requiredSeek} seconds!`);
      await this.play(new Date(), requiredSeek);

      this.jobs = [nodeSchedule.scheduleJob(endsAt, stop)];
    } else {
      log.debug(`Arming timer for ${this.compactTimestamp()} "${videoTitle}"`);

      this.jobs = [
        nodeSchedule.scheduleJob(
          "load",
          sub(startsAt, { seconds: 10 }),
          loadbg
        ),
        nodeSchedule.scheduleJob("start", startsAt, play),
        nodeSchedule.scheduleJob("stop", endsAt, stop),
      ];
    }
  }

  async disarm() {
    const { videoTitle } = this;

    log.debug(`Disarming: Video "${videoTitle}" at ${this.compactTimestamp()}`);

    for (const job of this.jobs) {
      log.debug(`Cancelling job ${job.name}`);
      job.cancel();
    }

    this.jobs = [];
  }
}

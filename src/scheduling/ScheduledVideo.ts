import { differenceInSeconds, sub } from "date-fns";
import type { ScheduleEntry } from "../generated/index.js";
import {
  CASPAR_MEDIA_URL_PREFIX,
  CHANNEL_FPS,
  VIDEO_LAYER,
} from "../config.js";
import { log } from "../log.js";
import { compactDate, compactTimestamp } from "./ScheduleLoader.js";
import type { ScheduleItem } from "./ScheduleLoader.js";
import { timeline } from "./Timeline.js";
import { connection } from "../caspar/connection.js";

export class ScheduledVideo implements ScheduleItem {
  startsAt: Date;
  endsAt: Date;
  itemType = "scheduledVideo" as const;
  label: string;

  constructor(private entry: ScheduleEntry) {
    this.startsAt = new Date(entry.startsAt);
    this.endsAt = new Date(entry.endsAt);
    this.label = entry.video.title!;
  }

  getFilename() {
    const asset = this.entry.video.media!.assets!.find(
      (x) => x.type === "broadcastable",
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

  play = async (_: Date, seekSeconds: number = 0) => {
    const seek = seekSeconds ? seekSeconds * CHANNEL_FPS : undefined;

    log.info(`Playing video "${this.entry.video.title}"`);

    await connection.play({
      ...VIDEO_LAYER,
      clip: this.getFilename(),
      seek,
    });
  };

  async arm() {
    const { startsAt, endsAt, stop, play, loadbg, label } = this;

    const now = new Date();

    if (endsAt <= now) {
      log.debug(
        `Not scheduling video "${label}" (end ${compactDate(
          endsAt,
        )} is in the past)`,
      );
      return;
    }

    if (startsAt <= now) {
      log.warn(`timer was armed while program should be active`);
      const requiredSeek = differenceInSeconds(now, startsAt);
      log.info(`playing immediately and seeking ${requiredSeek} seconds!`);
      await this.play(new Date(), requiredSeek);

      timeline.addEvent(this, endsAt, "stop", stop);
    } else {
      log.debug(`Arming timer for ${compactTimestamp(this)} "${label}"`);
      const loadsAt = sub(startsAt, { seconds: 10 });

      timeline.addEvent(this, loadsAt, "load", loadbg);
      timeline.addEvent(this, startsAt, "start", play);
      timeline.addEvent(this, endsAt, "stop", stop);
    }
  }

  async disarm() {
    const { label } = this;

    log.debug(`Disarming: Video "${label}" at ${compactTimestamp(this)}`);

    timeline.remove(this);
  }
}

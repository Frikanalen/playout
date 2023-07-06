import { add, sub, subMilliseconds } from "date-fns";
import { CG_LAYER, GRAPHICS_URL } from "../config.js";
import { log } from "../log.js";
import { connection } from "../connection.js";
import { compactDate, compactTimestamp } from "./ScheduleLoader.js";
import type { ScheduleItem } from "./ScheduleLoader.js";

import { timeline } from "./Timeline.js";

const wait = async (ms: number) =>
  new Promise((resolve) => setTimeout(resolve, ms));

export class InterstitialGraphics implements ScheduleItem {
  startsAt: Date;
  endsAt: Date;
  itemType = "graphics" as const;
  label = "Sendegrafikk";

  constructor(startsAt: Date, endsAt: Date) {
    this.startsAt = startsAt;
    this.endsAt = endsAt;
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
      log.debug(
        `Not scheduling graphics (${compactDate(endsAt)} is in the past)`,
      );
      return;
    }

    if (startsAt <= now) {
      log.warn(`Graphics ${compactTimestamp(this)} should be running`);

      log.info(`Arming graphics for ${compactTimestamp(this)}`);
      await load();
      // Wait a second before playing to allow the CG to load
      await wait(1000);

      log.info(`Playing graphics for ${compactTimestamp(this)}`);
      await play();

      timeline.addEvent(this, endsAt, "stop", stop);
      timeline.addEvent(this, clearAt, "clear", clear);
    } else {
      log.debug(`Arming graphics for ${compactTimestamp(this)}`);

      timeline.addEvent(this, loadAt, "load", load);
      timeline.addEvent(this, playAt, "start", play);
      timeline.addEvent(this, endsAt, "stop", stop);
      timeline.addEvent(this, clearAt, "clear", clear);
    }
  }

  async disarm() {
    await timeline.remove(this);
  }
}

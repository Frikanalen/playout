import { ScheduleEntry } from "../generated/index.js";
import { ScheduledVideo } from "./ScheduledVideo.js";
import { InterstitialGraphics } from "./InterstitialGraphics.js";
import { format } from "date-fns";
import { log } from "../log.js";
import { timeline } from "./Timeline.js";

export interface ScheduleItem {
  arm: () => Promise<void>;
  disarm: () => Promise<void>;
  startsAt: Date;
  endsAt: Date;
}

export const compactTimestamp = (item: ScheduleItem) => {
  const { startsAt, endsAt } = item;
  return format(startsAt, "HH:mm:ss.SSx - ") + format(endsAt, "HH:mm:ss.SSx");
};

export class Schedule {
  // Load a schedule from an array of ScheduleEntry objects
  // Clears and disarms any existing schedule
  load = async (entries: Array<ScheduleEntry>) => {
    if (timeline.getTimeline().length) await timeline.clear();

    log.info("Loading schedule");
    let previousEntryEnded: Date | undefined;

    for (const entry of entries) {
      const thisEntryStarts = new Date(entry.startsAt);

      await new ScheduledVideo(entry).arm();

      if (previousEntryEnded) {
        await new InterstitialGraphics(
          previousEntryEnded,
          thisEntryStarts
        ).arm();
      }

      previousEntryEnded = new Date(entry.endsAt);
    }
  };
}

import type { ScheduleEntry } from "../generated/index.js";
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
  itemType: "scheduledVideo" | "graphics";
  label: string;
}

export const compactTimestamp = (item: ScheduleItem) => {
  const { startsAt, endsAt } = item;
  return format(startsAt, "HH:mm:ss.SSx - ") + format(endsAt, "HH:mm:ss.SSx");
};

export const compactDate = (date: Date) => format(date, "HH:mm:ss.SSx");

// Feeds timeline with schedule items
export class ScheduleLoader {
  // Load a schedule from an array of ScheduleEntry objects
  // Clears and disarms any existing schedule
  load = async (entries: ScheduleEntry[]) => {
    log.info("Loading schedule");

    if (timeline.getEvents().length) timeline.clear();

    let prevEnds: Date | undefined;

    for (const entry of entries) {
      const entryStarts = new Date(entry.startsAt);

      await timeline.addItem(new ScheduledVideo(entry));

      if (prevEnds)
        await timeline.addItem(new InterstitialGraphics(prevEnds, entryStarts));

      prevEnds = new Date(entry.endsAt);
    }
  };
}

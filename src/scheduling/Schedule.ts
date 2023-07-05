import { ScheduleEntry } from "../generated/index.js";
import { ScheduledVideo } from "./ScheduledVideo.js";
import { InterstitialGraphics } from "./InterstitialGraphics.js";
import { fetchSchedule } from "./ScheduleFetcher.js";
import { endOfDay, startOfDay } from "date-fns";
import { log } from "../log.js";

export interface ScheduleItem {
  arm: () => Promise<void>;
  disarm: () => Promise<void>;
}

export class Schedule {
  scheduledEntries: ScheduleItem[] = [];

  add = async (entry: ScheduleItem) => {
    await entry.arm();
    this.scheduledEntries.push(entry);
  };

  clear = async () => {
    log.info("Clearing schedule jobs");
    await Promise.all(this.scheduledEntries.map((entry) => entry.disarm()));
    this.scheduledEntries = [];
  };

  // Load a schedule from an array of ScheduleEntry objects
  // Clears and disarms any existing schedule
  load = async (entries: Array<ScheduleEntry>) => {
    if (this.scheduledEntries.length) await this.clear();

    log.info("Loading schedule");
    let previousEntryEnded: Date | undefined;

    for (const entry of entries) {
      const thisEntryStarts = new Date(entry.startsAt);

      await this.add(new ScheduledVideo(entry));

      if (previousEntryEnded) {
        const interstitial = new InterstitialGraphics(
          previousEntryEnded,
          thisEntryStarts
        );

        await this.add(interstitial);
      }

      previousEntryEnded = new Date(entry.endsAt);
    }
  };

  start = () =>
    new Promise(async (resolve, reject) => {
      const now = new Date();
      const schedule = await fetchSchedule(startOfDay(now), endOfDay(now));
      await this.load(schedule);
    });
}

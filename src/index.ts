import { CasparCG } from "casparcg-connection";
import { OpenAPI, SchedulingService } from "./client";
import { Schedulable } from "./Schedulable";
import { CASPAR_HOST, FK_API } from "./config";
import { Logger } from "tslog";
import { InterstitialGraphics } from "./InterstitialGraphics";
import { ScheduledVideo } from "./ScheduledVideo";
import { endOfToday, startOfToday } from "date-fns";

export const log: Logger = new Logger();

OpenAPI.BASE = FK_API;

export const connection = new CasparCG(CASPAR_HOST);
const getSchedule = async () => {
  const schedule = await SchedulingService.getSchedule(
    startOfToday().toISOString(),
    endOfToday().toISOString()
  );

  if (!schedule.length) throw new Error(`Schedule loaded, contained 0 items!`);

  log.info(`Schedule loaded ${schedule.length} items.`);

  return schedule;
};

const get = async () => {
  const scheduledEntries: Schedulable[] = [];

  const addToSchedule = async (entry: Schedulable) => {
    await entry.arm();
    scheduledEntries.push(entry);
  };

  try {
    await connection.mixerClear(1);
    await connection.clear(1);

    const schedule = await getSchedule();

    let previousEntryEnded: Date | undefined;

    for (const entry of schedule) {
      const thisEntryStarts = new Date(entry.startsAt);

      await addToSchedule(new ScheduledVideo(entry));

      if (previousEntryEnded !== undefined) {
        await addToSchedule(
          new InterstitialGraphics(previousEntryEnded, thisEntryStarts)
        );
      }

      previousEntryEnded = new Date(entry.endsAt);
    }
  } catch (e) {
    log.error("error", e);
  }
};

(async () => {
  try {
    log.info(`Starting playout at ${new Date().toLocaleString()}`);
    var text = await get();
  } catch (e) {
    console.log(e);
    // Deal with the fact the chain failed
  }
})();

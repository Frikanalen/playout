import { CasparCG } from "casparcg-connection";
import { OpenAPI, SchedulingService } from "./generated";
import { Schedulable } from "./Schedulable";
import { CASPAR_HOST, FK_API } from "./config";
import { InterstitialGraphics } from "./InterstitialGraphics";
import { ScheduledVideo } from "./ScheduledVideo";
import { endOfToday, startOfToday } from "date-fns";
import process from "node:process";
import { log } from "./log.js";

OpenAPI.BASE = FK_API;

process
  .on("unhandledRejection", (reason, p) => {
    log.error(reason, "Unhandled Rejection at Promise", p);
  })
  .on("uncaughtException", (err) => {
    log.error(err, "Uncaught Exception thrown");
    process.exit(1);
  });

export const connection = new CasparCG({
  host: CASPAR_HOST,
});

const getSchedule = async () => {
  const schedule = await SchedulingService.getSchedule(
    startOfToday().toISOString(),
    endOfToday().toISOString()
  );

  if (!schedule.length)
    throw new Error(
      `Schedule for ${startOfToday().toISOString()}-${endOfToday().toISOString()}, contained 0 items!`
    );

  log.info(`Schedule loaded ${schedule.length} items.`);

  return schedule;
};

const initCaspar = async (connection: CasparCG) => {
  log.info(`Connecting to CasparCG host "${connection.host}"...`);
  await connection.connect();

  await connection.mixerClear({ channel: 1, layer: 50 });
  await connection.mixerClear({ channel: 1, layer: 60 });

  await connection.clear({ channel: 1 });
};

const runPlayout = async () => {
  const scheduledEntries: Schedulable[] = [];

  const addToSchedule = async (entry: Schedulable) => {
    await entry.arm();
    scheduledEntries.push(entry);
  };

  await initCaspar(connection);

  const schedule = await getSchedule();

  let previousEntryEnded: Date | undefined;

  for (const entry of schedule) {
    const thisEntryStarts = new Date(entry.startsAt);

    await addToSchedule(new ScheduledVideo(entry));

    if (typeof previousEntryEnded !== "undefined") {
      await addToSchedule(
        new InterstitialGraphics(previousEntryEnded!, thisEntryStarts)
      );
    }

    previousEntryEnded = new Date(entry.endsAt);
  }
};

(async () => {
  try {
    log.info(`Starting playout at ${new Date().toLocaleString()}`);
    await runPlayout();
  } catch (e) {
    log.error(e);
  }
})();

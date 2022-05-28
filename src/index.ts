import { CasparCG } from "casparcg-connection";
import { OpenAPI, SchedulingService } from "./client";
import { Schedulable } from "./Schedulable";
import { CASPAR_HOST, FK_API } from "./config";
import { Logger } from "tslog";
import { InterstitialGraphics } from "./InterstitialGraphics";
import { ScheduledVideo } from "./ScheduledVideo";
import { endOfToday, startOfToday } from "date-fns";
import process from "node:process";

export const log: Logger = new Logger();

OpenAPI.BASE = FK_API;

process
  .on("unhandledRejection", (reason, p) => {
    console.error(reason, "Unhandled Rejection at Promise", p);
  })
  .on("uncaughtException", (err) => {
    console.error(err, "Uncaught Exception thrown");
    process.exit(1);
  });

export const connection = new CasparCG({
  host: CASPAR_HOST,
  autoConnect: false,
  onConnected: () => log.info(`Connected to CasparCG "${CASPAR_HOST}"`),
  onDisconnected: () => log.info(`Disconnected from CasparCG "${CASPAR_HOST}"`),
  onError: (e) => log.warn(e),
  onLog: (msg) => log.debug(msg),
  autoReconnectAttempts: 1,
});

const getSchedule = async () => {
  const schedule = await SchedulingService.getSchedule(
    startOfToday().toISOString(),
    endOfToday().toISOString()
  );

  if (!schedule.length) throw new Error(`Schedule loaded, contained 0 items!`);

  log.info(`Schedule loaded ${schedule.length} items.`);

  return schedule;
};

const initCaspar = async (connection: CasparCG) => {
  await connection.mixerClear(1);
  await connection.clear(1);
};

const runPlayout = async () => {
  const scheduledEntries: Schedulable[] = [];

  const addToSchedule = async (entry: Schedulable) => {
    await entry.arm();
    scheduledEntries.push(entry);
  };

  try {
    log.info(`Connecting to CasparCG host "${connection.host}"...`);
    await connection.connect();

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
  } catch (e) {
    log.error("error", e);
  }
};

(async () => {
  try {
    log.info(`Starting playout at ${new Date().toLocaleString()}`);
    await runPlayout();
  } catch (e) {
    console.log(e);
  }
})();

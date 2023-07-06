import { ScheduledVideo } from "./ScheduledVideo.js";
import type { ScheduleEntry } from "../generated/index.js";
import { add, sub } from "date-fns";
import { CHANNEL_FPS, VIDEO_LAYER } from "../config.js";
import { connection } from "../connection.js";
import { timeline } from "./Timeline.js";
import { makeTestVideo } from "./testUtils.js";

// mock out connection to CasparCG
jest.mock("../connection.js", () => {
  return {
    connection: {
      loadbg: jest.fn(),
      stop: jest.fn(),
      play: jest.fn(),
    },
  };
});

// Mock out the timeline
jest.mock("../scheduling/Timeline.js", () => {
  return {
    timeline: {
      addEvent: jest.fn(),
      remove: jest.fn(),
    },
  };
});

// Reset mock before every test
beforeEach(() => {
  jest.clearAllMocks();
});

const makeTestScheduleEntry = (startsAt: Date, endsAt: Date): ScheduleEntry => {
  return {
    type: "video",
    startsAt: startsAt.toISOString(),
    endsAt: endsAt.toISOString(),
    video: makeTestVideo(),
  };
};

it("can be created", () => {
  const startsAt = new Date();
  const endsAt = add(startsAt, { seconds: 10 });
  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);
  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  expect(scheduledVideo).toBeDefined();
});

it("creates no jobs if in the past", async () => {
  const startsAt = sub(new Date(), { days: 1 });
  const endsAt = add(startsAt, { seconds: 10 });

  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  expect(scheduledVideo).toBeDefined();
  await scheduledVideo.arm();
  expect(timeline.addEvent).not.toHaveBeenCalled();
});
it("creates three jobs at the right times if in the future", async () => {
  const startsAt = add(new Date(), { days: 1 });
  const loadsAt = sub(startsAt, { seconds: 10 });
  const endsAt = add(startsAt, { seconds: 10 });

  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  await scheduledVideo.arm();
  // Check that Timeline.addEvent() is called with the right arguments
  expect(timeline.addEvent).toHaveBeenCalledTimes(3);
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    1,
    scheduledVideo,
    loadsAt,
    "load",
    scheduledVideo.loadbg,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    2,
    scheduledVideo,
    startsAt,
    "start",
    scheduledVideo.play,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    3,
    scheduledVideo,
    endsAt,
    "stop",
    scheduledVideo.stop,
  );
});

it("calls play immediately when armed if video is presently playing", async () => {
  // generate a random number between 1 and 1000
  const randomSeconds = Math.floor(Math.random() * 1000) + 1;

  const startsAt = sub(new Date(), { seconds: randomSeconds });
  const endsAt = add(startsAt, { hours: 1 });

  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  await scheduledVideo.arm();

  // verify that timeline.addEvent() is called with stopsAt
  expect(timeline.addEvent).toHaveBeenCalledWith(
    scheduledVideo,
    endsAt,
    "stop",
    scheduledVideo.stop,
  );

  // verify that connection.play() is called after arm()
  expect(connection.play).toHaveBeenCalledTimes(1);

  // verify that connection.play() is called with the right arguments
  expect(connection.play).toHaveBeenCalledWith({
    ...VIDEO_LAYER,
    clip: "test.mp4",
    seek: randomSeconds * CHANNEL_FPS,
  });
});

it("Has zero jobs after disarming", async () => {
  const startsAt = add(new Date(), { days: 1 });
  const endsAt = add(startsAt, { seconds: 10 });
  const loadsAt = sub(startsAt, { seconds: 10 });
  const scheduleEntry = makeTestScheduleEntry(startsAt, endsAt);

  const scheduledVideo = new ScheduledVideo(scheduleEntry);
  await scheduledVideo.arm();

  // Check that Timeline.addEvent() is called with the right arguments
  expect(timeline.addEvent).toHaveBeenCalledTimes(3);

  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    1,
    scheduledVideo,
    loadsAt,
    "load",
    scheduledVideo.loadbg,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    2,
    scheduledVideo,
    startsAt,
    "start",
    scheduledVideo.play,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    3,
    scheduledVideo,
    endsAt,
    "stop",
    scheduledVideo.stop,
  );

  await scheduledVideo.disarm();
  expect(timeline.remove).toHaveBeenCalledWith(scheduledVideo);
});

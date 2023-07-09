import { InterstitialGraphics } from "./InterstitialGraphics.js";
import { add, sub, subMilliseconds } from "date-fns";
import { timeline } from "./Timeline.js";

// mock out CasparCG
jest.mock("../caspar.js", () => {
  return {
    connection: {
      cgAdd: jest.fn(async () => {}),
      cgPlay: jest.fn(),
      cgStop: jest.fn(),
      cgClear: jest.fn(),
    },
  };
});

// Reset mock before every test
beforeEach(() => {
  jest.clearAllMocks();
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

// Set mock CG URL environment variable
process.env["GRAPHICS_URL"] = "http://localhost:3000/graphics";

it("can be created", () => {
  const startsAt = new Date();
  const endsAt = add(startsAt, { seconds: 10 });

  const graphics = new InterstitialGraphics(startsAt, endsAt);

  expect(graphics).toBeDefined();
});

it("generates no jobs if the end time is in the past", () => {
  const startsAt = new Date();
  const endsAt = add(startsAt, { seconds: -10 });

  const graphics = new InterstitialGraphics(startsAt, endsAt);

  expect(graphics).toBeDefined();
  expect(timeline.addEvent).not.toHaveBeenCalled();
});

it("Generates correct load, play, stop and clear jobs if in future", async () => {
  const startsAt = add(new Date(), { days: 1 });
  const loadsAt = sub(startsAt, { seconds: 1 });
  const endsAt = add(startsAt, { seconds: 10 });
  const clearsAt = add(endsAt, { seconds: 2 });

  const graphics = new InterstitialGraphics(startsAt, endsAt);
  await graphics.arm();

  // Check that the correct number of items are added to timeline
  expect(timeline.addEvent).toHaveBeenCalledTimes(4);

  // Check that the correct items are added to timeline
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    1,
    graphics,
    loadsAt,
    "load",
    graphics.load,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    2,
    graphics,
    subMilliseconds(startsAt, 500),
    "start",
    graphics.play,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    3,
    graphics,
    endsAt,
    "stop",
    graphics.stop,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    4,
    graphics,
    clearsAt,
    "clear",
    graphics.clear,
  );
});

it("immediately plays if start time in past and end time in future", async () => {
  const startsAt = sub(new Date(), { seconds: 10 });
  const endsAt = add(startsAt, { seconds: 1000 });
  const clearsAt = add(endsAt, { seconds: 2 });

  const graphics = new InterstitialGraphics(startsAt, endsAt);
  await graphics.arm();

  // Check that the correct number of items are added to timeline
  expect(timeline.addEvent).toHaveBeenCalledTimes(2);

  // Check that the correct items are added to timeline
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    1,
    graphics,
    endsAt,
    "stop",
    graphics.stop,
  );
  expect(timeline.addEvent).toHaveBeenNthCalledWith(
    2,
    graphics,
    clearsAt,
    "clear",
    graphics.clear,
  );
});

it("removes itself from timeline when disarmed", async () => {
  const startsAt = add(new Date(), { days: 1 });
  const endsAt = add(startsAt, { seconds: 10 });

  const graphics = new InterstitialGraphics(startsAt, endsAt);
  await graphics.arm();

  expect(timeline.addEvent).toHaveBeenCalledTimes(4);

  await graphics.disarm();

  expect(timeline.remove).toHaveBeenCalledWith(graphics);
});

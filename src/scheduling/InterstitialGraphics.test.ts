import { InterstitialGraphics } from "./InterstitialGraphics.js";
import { add, sub, subMilliseconds } from "date-fns";

// mock out connection to CasparCG
jest.mock("../connection.js", () => {
  return {
    connection: {
      cgAdd: jest.fn(async () => {}),
      cgPlay: jest.fn(),
      cgStop: jest.fn(),
      cgClear: jest.fn(),
    },
  };
});

// Set mock CG URL environment variable
process.env.GRAPHICS_URL = "http://localhost:3000/graphics";

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

  expect(graphics.getJobs()).toHaveLength(0);
});

it("Generates correct load, play, stop and clear jobs if in future", async () => {
  const startsAt = add(new Date(), { days: 1 });
  const loadsAt = sub(startsAt, { seconds: 1 });
  const endsAt = add(startsAt, { seconds: 10 });
  const clearsAt = add(endsAt, { seconds: 2 });

  const graphics = new InterstitialGraphics(startsAt, endsAt);
  await graphics.arm();

  expect(graphics.getJobs()).toHaveLength(4);

  const [loadJob, startJob, stopJob, clearJob] = graphics.getJobs();

  expect(loadJob.nextInvocation().getTime()).toBe(loadsAt.getTime());
  expect(startJob.nextInvocation().getTime()).toBe(
    subMilliseconds(startsAt, 500).getTime()
  );
  expect(stopJob.nextInvocation().getTime()).toBe(endsAt.getTime());
  expect(clearJob.nextInvocation().getTime()).toBe(clearsAt.getTime());
});

it("immediately plays if start time in past and end time in future", async () => {
  const startsAt = sub(new Date(), { seconds: 10 });
  const endsAt = add(startsAt, { seconds: 1000 });
  const clearsAt = add(endsAt, { seconds: 2 });

  const graphics = new InterstitialGraphics(startsAt, endsAt);
  await graphics.arm();

  expect(graphics.getJobs()).toHaveLength(2);

  const [stopJob, clearJob] = graphics.getJobs();

  expect(stopJob.nextInvocation().getTime()).toBe(endsAt.getTime());
  expect(clearJob.nextInvocation().getTime()).toBe(clearsAt.getTime());
});

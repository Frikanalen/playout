import { makeTestSchedule } from "./testUtils.js";
import { ScheduleLoader } from "./ScheduleLoader.js";
import { endOfDay, startOfDay } from "date-fns";

// Mock out the SchedulingService
jest.mock("../generated/index.js", () => ({
  SchedulingService: {
    getSchedule: jest.fn((start, end) => makeTestSchedule(start, end)),
  },
}));

// Mock out the timeline
jest.mock("./Timeline.js", () => ({
  timeline: {
    addEvent: jest.fn(),
    addItem: jest.fn(),
    remove: jest.fn(),
    getEvents: jest.fn(() => []),
  },
}));

it("can be created", () => {
  const schedule = new ScheduleLoader();
  expect(schedule).toBeDefined();
});

it("can load a schedule", async () => {
  const now = new Date();

  const schedule = new ScheduleLoader();
  const testSchedule = makeTestSchedule(
    startOfDay(now).toISOString(),
    endOfDay(now).toISOString(),
  );
  await schedule.load(testSchedule);
  expect(schedule).toBeDefined();
});

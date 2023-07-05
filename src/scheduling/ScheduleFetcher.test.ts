import { fetchSchedule } from "./ScheduleFetcher.js";
import { addMilliseconds, endOfDay, startOfDay } from "date-fns";
import { makeTestVideo } from "./ScheduledVideo.test.js";

// Generate test schedule
const makeTestSchedule = (start: string, end: string) => {
  const schedule = [];
  let current = new Date(start);
  const endDate = new Date(end);

  while (current < endDate) {
    // Random program duration between 40ms and 1 hour
    const randomDuration = Math.floor(Math.random() * 3600000) + 40;

    const endsAt = addMilliseconds(current, randomDuration);

    schedule.push({
      type: "video",
      startsAt: current.toISOString(),
      endsAt: endsAt.toISOString(),
      video: { ...makeTestVideo(), duration: randomDuration * 1000 },
    });

    // Random gap between 0ms and 5 minutes
    const randomGap = Math.floor(Math.random() * 300000);

    current = addMilliseconds(endsAt, randomGap);
  }

  return schedule;
};

// Mock out the SchedulingService
jest.mock("../generated/index.js", () => {
  return {
    SchedulingService: {
      getSchedule: jest.fn((start, end) => makeTestSchedule(start, end)),
    },
  };
});

it("fetches the schedule", async () => {
  const now = new Date();
  const schedule = await fetchSchedule(startOfDay(now), endOfDay(now));
  expect(schedule.length).toBeGreaterThan(0);
  // Ensure the ScheduleService is called
  expect(
    require("../generated/index.js").SchedulingService.getSchedule
  ).toBeCalled();
});

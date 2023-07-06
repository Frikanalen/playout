import { Timeline } from "./Timeline.js";

let timeline: Timeline;

// mock out the nodeSchedule
jest.mock("node-schedule", () => ({
  scheduleJob: jest.fn(() => "job"),
}));

// reset timeline before every test
beforeEach(() => {
  timeline = new Timeline();
});

it("should be empty when first created", () => {
  expect(timeline.getEvents()).toEqual([]);
});

it("should addEvent a single item", () => {
  const scheduleItem = {
    startsAt: new Date("2020-01-01T00:00:00.000Z"),
    endsAt: new Date("2020-01-01T00:00:00.000Z"),
    arm: jest.fn(),
    disarm: jest.fn(),
  };

  const item = {
    item: scheduleItem,
    fireAt: new Date("2020-01-01T00:00:00.000Z"),
    eventLabel: "test",
    cb: jest.fn(),
  };

  timeline.addEvent(item.item, item.fireAt, item.eventLabel, item.cb);

  expect(timeline.getEvents()).toEqual([
    {
      item: item.item,
      fireAt: item.fireAt,
      eventLabel: item.eventLabel,
      job: "job",
    },
  ]);
});

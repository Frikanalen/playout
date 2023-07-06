import type {
  CgAddParameters,
  CgClearParameters,
  CgPlayParameters,
  CgStopParameters,
  ClearParameters,
  InfoParameters,
  LoadParameters,
  MixerClearParameters,
  PlayParameters,
  StopParameters,
} from "casparcg-connection/dist/parameters.js";
import type { Response, SendResult } from "casparcg-connection";
import { log } from "../log.js";

const fakeSendResult = () => ({
  error: undefined,
  request: undefined as unknown as Promise<Response>,
});
const fakeCommand =
  <T>(command: string) =>
  async (args: T): Promise<SendResult> => {
    log.debug(`Fake CasparCG command: ${command} called with ${args}`);
    return fakeSendResult();
  };
// Mock CasparCG connection which does nothing but log events
export const fakeCaspar = {
  host: "DUMMY HOST",
  cgAdd: fakeCommand<CgAddParameters>("cgAdd"),
  cgPlay: fakeCommand<CgPlayParameters>("cgPlay"),
  cgStop: fakeCommand<CgStopParameters>("cgStop"),
  cgClear: fakeCommand<CgClearParameters>("cgClear"),
  play: fakeCommand<PlayParameters>("play"),
  loadbg: fakeCommand<LoadParameters>("loadbg"),
  stop: fakeCommand<StopParameters>("stop"),
  clear: fakeCommand<ClearParameters>("clear"),
  mixerClear: fakeCommand<MixerClearParameters>("mixerClear"),
  info: fakeCommand<InfoParameters>("info"),
  connect: async () => {
    log.info("Fake CasparCG connection established");
  },
};

import type { SendResult, Response } from "casparcg-connection";
// import { CASPAR_HOST } from "./config.js";
import type {
  CgAddParameters,
  CgClearParameters,
  CgPlayParameters,
  CgStopParameters,
  LoadParameters,
  PlayParameters,
  StopParameters,
  ClearParameters,
  MixerClearParameters,
  InfoParameters,
} from "casparcg-connection/dist/parameters.js";

/*export const connection = new CasparCG({
  host: CASPAR_HOST,
});
*/

const fakeSendResult = () => ({
  error: undefined,
  request: undefined as unknown as Promise<Response>,
});

const fakeCommand = async <T>(_: T): Promise<SendResult> => {
  return fakeSendResult();
};

// Mock CasparCG connection which does nothing but log events
export const connection = {
  host: "DUMMY HOST",
  cgAdd: fakeCommand<CgAddParameters>,
  cgPlay: fakeCommand<CgPlayParameters>,
  cgStop: fakeCommand<CgStopParameters>,
  cgClear: fakeCommand<CgClearParameters>,
  play: fakeCommand<PlayParameters>,
  loadbg: fakeCommand<LoadParameters>,
  stop: fakeCommand<StopParameters>,
  clear: fakeCommand<ClearParameters>,
  mixerClear: fakeCommand<MixerClearParameters>,
  info: fakeCommand<InfoParameters>,
  connect: () => {},
};

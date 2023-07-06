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

const fakeSendResult = () => ({
  error: undefined,
  request: undefined as unknown as Promise<Response>,
});
const fakeCommand = async <T>(_: T): Promise<SendResult> => {
  return fakeSendResult();
};
// Mock CasparCG connection which does nothing but log events
export const fakeCaspar = {
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

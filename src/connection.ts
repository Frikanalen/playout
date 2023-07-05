import { CasparCG } from "casparcg-connection";
import { CASPAR_HOST } from "./config.js";

export const connection = new CasparCG({
  host: CASPAR_HOST,
});

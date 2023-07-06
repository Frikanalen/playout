import { CASPAR_HOST } from "../config.js";
import { CasparCG } from "casparcg-connection";
import { fakeCaspar } from "./mockCaspar.js";
import { log } from "../log.js";

const getConnection = () => {
  if (!CASPAR_HOST) {
    if (process.env["NODE_ENV"] === "production")
      throw new Error("No CasparCG host configured");

    log.warn("No CasparCG host configured, using fake connection");
    return fakeCaspar;
  }

  return new CasparCG({ host: CASPAR_HOST });
};

export const connection = getConnection();

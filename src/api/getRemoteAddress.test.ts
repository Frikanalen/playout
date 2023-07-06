import { getRemoteAddress } from "./getRemoteAddress";

describe("getRemoteAddress", () => {
  it("should return the remote address if no X-Forwarded-For header is present", () => {
    const incoming = {
      socket: {
        remoteAddress: "1234",
      },
      headers: {},
    };
    expect(getRemoteAddress(incoming as any)).toEqual("1234");
  });

  it("should return the X-Forwarded-For header if present", () => {
    const incoming = {
      socket: {
        remoteAddress: "1234",
      },
      headers: {
        "x-forwarded-for": ["5678"],
      },
    };
    expect(getRemoteAddress(incoming as any)).toEqual("5678");
  });

  it("should return semicolon-delimited list if multiple X-Forwarded-For headers are present", () => {
    const incoming = {
      socket: {
        remoteAddress: "1234",
      },
      headers: {
        "x-forwarded-for": ["5678", "9012"],
      },
    };
    expect(getRemoteAddress(incoming as any)).toEqual("5678;9012");
  });
});

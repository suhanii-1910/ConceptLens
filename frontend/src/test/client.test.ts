import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, request } from "../api/client";

afterEach(() => vi.unstubAllGlobals());
describe("API failures", () => {
  it("also removes internal content from validation arrays", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({
              detail: [
                { msg: "reasoning_steps cannot contain blank steps" },
                { msg: "Traceback: internal provider exception" },
              ],
            }),
            { status: 422 },
          ),
        ),
    );
    await expect(request("/test")).rejects.toMatchObject({
      validation: ["reasoning_steps cannot contain blank steps"],
    });
  });
  it.each([404, 409, 415, 422, 502, 503])(
    "preserves useful safe FastAPI details for %s",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(
            JSON.stringify({
              detail: "Question has no usable source evidence.",
            }),
            { status },
          ),
        ),
      );
      await expect(request("/test")).rejects.toMatchObject({
        status,
        detail: "Question has no usable source evidence.",
      });
    },
  );
  it.each([
    "Traceback: provider crashed",
    "asyncpg failed at /private/db/schema",
    "api_key=not-a-real-key",
    "SELECT * FROM users",
  ])("does not display internal details: %s", async (detail) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail }), { status: 503 }),
        ),
    );
    await expect(request("/test")).rejects.toMatchObject({ detail: null });
  });
  it("retains validation messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              {
                loc: ["body", "reasoning_text"],
                msg: "String should have at most 8000 characters",
              },
            ],
          }),
          { status: 422 },
        ),
      ),
    );
    await expect(request("/test")).rejects.toMatchObject({
      validation: ["String should have at most 8000 characters"],
    });
  });
  it("handles network failures and malformed JSON without exposing response bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(request("/test")).rejects.toMatchObject({ status: 0 });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("<html>Internal proxy details</html>", { status: 502 }),
        ),
    );
    await expect(request("/test")).rejects.toEqual(new ApiError(502));
  });
  it("preserves AbortError and forwards the cancellation signal", async () => {
    const abort = new DOMException("Aborted", "AbortError");
    const fetcher = vi.fn().mockRejectedValue(abort);
    vi.stubGlobal("fetch", fetcher);
    const controller = new AbortController();
    await expect(request("/test", { signal: controller.signal })).rejects.toBe(
      abort,
    );
    expect(fetcher.mock.calls[0][1].signal).toBe(controller.signal);
  });
});

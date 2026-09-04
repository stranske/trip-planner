import { afterEach, expect, it, vi } from "vitest";

import { fetchWorkspace } from "./workspace";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

it("loads the saved workspace from a configured API origin with session credentials", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/base/");
  const workspacePayload = {
    trip_record: {
      trip: {
        trip_id: "trip:kyoto",
      },
    },
  };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(workspacePayload),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(fetchWorkspace("trip:kyoto")).resolves.toEqual(workspacePayload);

  expect(fetchMock).toHaveBeenCalledWith(
    "https://api.example.test/api/workspace/trip:kyoto",
    expect.objectContaining({ credentials: "include" })
  );
});

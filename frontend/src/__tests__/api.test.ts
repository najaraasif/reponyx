import { api, APIError } from "@/lib/api";

const mockFetch = jest.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

function mockResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

describe("API Client", () => {
  describe("health", () => {
    it("returns health response", async () => {
      const data = { status: "ok", service: "Reponyx", version: "0.1.0", environment: "development" };
      mockFetch.mockReturnValue(mockResponse(data));
      const result = await api.health();
      expect(result.service).toBe("Reponyx");
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining("/healthz"), expect.anything());
    });
  });

  describe("llmHealth", () => {
    it("returns LLM health response", async () => {
      const data = { provider: "mock", model: "gpt-4.1-mini", available: true, status: "configured" };
      mockFetch.mockReturnValue(mockResponse(data));
      const result = await api.llmHealth();
      expect(result.provider).toBe("mock");
      expect(result.available).toBe(true);
    });
  });

  describe("repositories", () => {
    it("lists repositories", async () => {
      mockFetch.mockReturnValue(mockResponse([]));
      const result = await api.repositories.list();
      expect(Array.isArray(result)).toBe(true);
    });

    it("creates a repository", async () => {
      const data = { id: "abc123", url: "https://github.com/psf/requests", status: "created" };
      mockFetch.mockReturnValue(mockResponse(data, 201));
      const result = await api.repositories.create("https://github.com/psf/requests");
      expect(result.id).toBe("abc123");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/repositories"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("throws on invalid URL", async () => {
      mockFetch.mockReturnValue(mockResponse({ detail: "Invalid URL" }, 422));
      await expect(api.repositories.create("bad-url")).rejects.toThrow(APIError);
    });
  });

  describe("repairs", () => {
    it("lists repairs", async () => {
      mockFetch.mockReturnValue(mockResponse([]));
      const result = await api.repairs.list();
      expect(Array.isArray(result)).toBe(true);
    });

    it("approves a repair", async () => {
      mockFetch.mockReturnValue(mockResponse({}));
      await api.repairs.approve("repair-123");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/repairs/repair-123/approve"),
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("rejects a repair", async () => {
      mockFetch.mockReturnValue(mockResponse({}));
      await api.repairs.reject("repair-123");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/repairs/repair-123/reject"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  describe("error handling", () => {
    it("throws APIError on non-ok response", async () => {
      mockFetch.mockReturnValue(mockResponse({ detail: "not found" }, 404));
      await expect(api.repositories.get("missing")).rejects.toThrow(APIError);
    });

    it("includes status in APIError", async () => {
      mockFetch.mockReturnValue(mockResponse({ detail: "error" }, 500));
      try {
        await api.health();
        fail("should have thrown");
      } catch (e) {
        expect(e).toBeInstanceOf(APIError);
        expect((e as APIError).status).toBe(500);
      }
    });
  });
});
